"""The phone page (inline HTML/JS, no build step).

The page is the input device, and it has two input modes, like a Discord
client:

- **Push-to-talk** — hold the button; audio crosses the wire only while
  held. The hold edges are the exact turn boundary.
- **Voice activity** — open mic; a simple level gate in the page opens
  when you speak and closes after a short hangover. The gate edges POST
  the same down/up as the button, so the bridge and its consumers see no
  difference between the modes.

Either way the page:
  1. POSTs gate edges + heartbeats to /voice/ptt[/heartbeat].
  2. Streams gated mic audio as binary s16le 48 kHz mono over
     WS /voice/page/audio.
  3. Plays back binary s16le 48 kHz mono received on the same socket.

The live-ring indicator is decoupled from the modes: a meter measures mic
level, a gate decides transmission, and the ring shows gate && level.

NOTE: getUserMedia requires a secure context. Over plain HTTP on a LAN IP
the mic is unavailable (iOS Safari especially) — serve the page over
HTTPS (e.g. `tailscale serve`) or use localhost. The page says so when it
detects this instead of failing silently.
"""

from __future__ import annotations

PTT_PAGE = """<!doctype html>
<html lang="en"><head>
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>voice-bridge</title>
<style>
  body { margin:0; height:100vh; display:flex; flex-direction:column; gap:18px;
         align-items:center; justify-content:center; background:#1e1f22; color:#dbdee1;
         font-family:system-ui,sans-serif; }
  #modes { display:flex; border-radius:8px; overflow:hidden; border:1px solid #3f4147; }
  #modes button { border:none; padding:10px 18px; font-size:.95rem; font-weight:600;
         background:#2b2d31; color:#949ba4; cursor:pointer; }
  #modes button.on { background:#5865f2; color:white; }
  #btn { width:70vw; max-width:320px; aspect-ratio:1; border-radius:50%; border:none;
         font-size:1.4rem; font-weight:600; background:#5865f2; color:white;
         touch-action:none; user-select:none; -webkit-user-select:none;
         transition:box-shadow .12s ease-out; }
  #btn.down { background:#3ba55d; }
  /* The "Discord ring": lit while the gate is open AND the mic hears you. */
  #btn.live { box-shadow:0 0 0 8px #23a55a; }
  #btn.live.loud { box-shadow:0 0 0 14px rgba(35,165,90,.55); }
  #status { opacity:.75; font-size:.9rem; max-width:80vw; text-align:center; }
</style></head><body>
<div id="modes">
  <button id="m-ptt">Push to talk</button>
  <button id="m-auto">Voice activity</button>
</div>
<button id="btn">Hold to talk</button>
<div id="status">connecting…</div>
<script>
const token = new URLSearchParams(location.search).get("token") || "";
const btn = document.getElementById("btn");
const status = document.getElementById("status");
const modeBtns = { ptt: document.getElementById("m-ptt"), auto: document.getElementById("m-auto") };

// ---- decoupled pieces: meter, gate, display -----------------------------
let level = 0;          // smoothed mic RMS (the meter — knows no modes)
let down = false;       // physical hold
let tx = false;         // the gate: audio crosses the wire only when true
let mode = localStorage.getItem("vb-mode") || "ptt";

const VAD_OPEN = 0.02;    // RMS that counts as "voice present"
const VAD_HANGOVER_MS = 800;  // silence this long closes the gate (auto mode)
let lastVoiceAt = 0;

async function send(state) {
  try {
    const r = await fetch("/voice/ptt", {method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({state, token})});
    if (!r.ok) status.textContent = "rejected (" + r.status + ")";
  } catch { status.textContent = "unreachable"; }
}
function setTx(on) {           // gate edges look identical to the bridge,
  if (tx === on) return;       // whichever mode produced them
  tx = on;
  send(on ? "down" : "up");
}
function setMode(m) {
  mode = m;
  localStorage.setItem("vb-mode", m);
  modeBtns.ptt.classList.toggle("on", m === "ptt");
  modeBtns.auto.classList.toggle("on", m === "auto");
  btn.textContent = m === "ptt" ? "Hold to talk" : "Just talk";
  setTx(false);
  updateStatus();
  initAudio();  // a tap on the toggle is also a user gesture
}
function updateStatus() {
  if (!audioReady) return;
  status.textContent = mode === "ptt"
    ? "hold the button and talk"
    : "listening — just talk";
}
modeBtns.ptt.addEventListener("click", () => setMode("ptt"));
modeBtns.auto.addEventListener("click", () => setMode("auto"));

// The display: gate && level, refreshed on a timer — knows nothing about
// which mode opened the gate.
setInterval(() => {
  const live = tx && level > VAD_OPEN;
  btn.classList.toggle("live", live);
  btn.classList.toggle("loud", live && level > VAD_OPEN * 3);
}, 100);

// Auto mode: the level meter drives the gate (this is the whole "VAD").
setInterval(() => {
  if (mode !== "auto" || !audioReady) return;
  const now = performance.now();
  if (level > VAD_OPEN) { lastVoiceAt = now; setTx(true); }
  else if (tx && now - lastVoiceAt > VAD_HANGOVER_MS) setTx(false);
}, 100);

// PTT: the hold drives the gate.
function press(e) { e.preventDefault(); initAudio();
  if (mode !== "ptt" || down) return;
  down = true; btn.classList.add("down"); btn.textContent = "Talking…";
  lastVoiceAt = performance.now(); setTx(true); }
function release(e) { if (e) e.preventDefault();
  if (!down) return;
  down = false; btn.classList.remove("down");
  btn.textContent = mode === "ptt" ? "Hold to talk" : "Just talk";
  if (mode === "ptt") setTx(false); }
btn.addEventListener("pointerdown", press);
addEventListener("pointerup", release);
addEventListener("pointercancel", release);

setInterval(() => fetch("/voice/ptt/heartbeat", {method:"POST",
  headers:{"Content-Type":"application/json"}, body: JSON.stringify({token})}), 3000);

// ---- duplex audio over one websocket (s16le 48 kHz mono both ways) ----
const workletSrc = `
class Pcm extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      let sum = 0;
      const buf = new Int16Array(ch.length);
      for (let i = 0; i < ch.length; i++) {
        const s = Math.max(-1, Math.min(1, ch[i]));
        buf[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        sum += s * s;
      }
      this.port.postMessage({pcm: buf.buffer, rms: Math.sqrt(sum / ch.length)},
                            [buf.buffer]);
    }
    return true;
  }
}
registerProcessor("pcm", Pcm);`;

let audioReady = false, audioStarting = false;
let ws = null;
let nextPlayTime = 0;
let ctx = null;

async function initAudio() {
  if (audioReady || audioStarting) return;
  audioStarting = true;
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("mic unavailable on plain http:// — open this page over " +
                      "HTTPS (e.g. the tailscale serve URL) or localhost");
    }
    if (!ctx) ctx = new AudioContext({sampleRate: 48000});
    // iOS suspends AudioContext until a user gesture; awaiting resume()
    // outside one can hang forever and jam initAudio. Fire and forget —
    // the pointerdown listener below keeps retrying on every tap.
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    await ctx.audioWorklet.addModule(
      URL.createObjectURL(new Blob([workletSrc], {type: "application/javascript"})));
    const src = ctx.createMediaStreamSource(stream);
    const node = new AudioWorkletNode(ctx, "pcm");
    src.connect(node);
    node.connect(ctx.destination);  // required for the worklet to run; mic is not audible

    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/voice/page/audio?token=${encodeURIComponent(token)}`);
    ws.binaryType = "arraybuffer";
    node.port.onmessage = (ev) => {
      level = level * 0.7 + ev.data.rms * 0.3;   // the meter always runs…
      if (tx && ws.readyState === WebSocket.OPEN) ws.send(ev.data.pcm);  // …the gate decides
    };
    ws.onmessage = (ev) => playPcm(ev.data);
    ws.onclose = () => { audioReady = false; status.textContent = "audio disconnected — reopen the page"; };
    ws.onerror = () => { status.textContent = "audio socket error"; };
    ws.onopen = () => { audioReady = true; updateStatus(); };
  } catch (err) {
    status.textContent = "mic failed: " + (err && err.message ? err.message : err);
  }
  audioStarting = false;
}

// iOS suspends AudioContext until a user gesture; every tap re-tries.
document.addEventListener("pointerdown", () => {
  if (ctx && ctx.state === "suspended") ctx.resume().catch(() => {});
  initAudio();
});
initAudio();  // getUserMedia prompt can show on load; ctx resumes on first tap

function playPcm(data) {
  if (!ctx) return;
  const pcm = new Int16Array(data);
  const buf = ctx.createBuffer(1, pcm.length, ctx.sampleRate);
  const out = buf.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) out[i] = pcm[i] / 0x8000;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.connect(ctx.destination);
  nextPlayTime = Math.max(nextPlayTime, ctx.currentTime);
  src.start(nextPlayTime);
  nextPlayTime += buf.duration;
}

setMode(mode);  // reflect the persisted mode
</script></body></html>"""
