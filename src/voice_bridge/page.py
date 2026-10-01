"""The hold-to-talk phone page (inline HTML/JS, no build step).

The page does three things:
  1. POSTs press/release + heartbeats to /voice/ptt[/heartbeat] — the
     exact turn boundary (moved here from teaching-agent's /ptt page).
  2. While held, captures mic audio and streams it as binary s16le
     48 kHz mono over WS /voice/page/audio.
  3. Plays back binary s16le 48 kHz mono received on the same socket.

Audio uses getUserMedia + an AudioWorklet (loaded from a Blob URL so the
page stays a single file). The mic is only *sent* while the button is
held — the hold is the mic gate AND the turn boundary.
"""

from __future__ import annotations

PTT_PAGE = """<!doctype html>
<html lang="en"><head>
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>voice-bridge</title>
<style>
  body { margin:0; height:100vh; display:flex; flex-direction:column; gap:16px;
         align-items:center; justify-content:center; background:#1e1f22; color:#dbdee1;
         font-family:system-ui,sans-serif; }
  #btn { width:70vw; max-width:320px; aspect-ratio:1; border-radius:50%; border:none;
         font-size:1.4rem; font-weight:600; background:#5865f2; color:white;
         touch-action:none; user-select:none; -webkit-user-select:none; }
  #btn.down { background:#23a55a; }
  #status { opacity:.7; font-size:.9rem; }
</style></head><body>
<button id="btn">Hold to talk</button>
<div id="status">connecting…</div>
<script>
const token = new URLSearchParams(location.search).get("token") || "";
const btn = document.getElementById("btn");
const status = document.getElementById("status");
let down = false;

// ---- PTT: press/release + heartbeat (exact turn boundary) ----
async function send(state) {
  try {
    const r = await fetch("/voice/ptt", {method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({state, token})});
    status.textContent = r.ok ? (down ? "listening…" : "connected") : "rejected (" + r.status + ")";
  } catch { status.textContent = "unreachable"; }
}
function press(e) { e.preventDefault(); if (!down) { down = true;
  btn.classList.add("down"); btn.textContent = "Talking…"; send("down"); startAudio(); } }
function release(e) { e.preventDefault(); if (down) { down = false;
  btn.classList.remove("down"); btn.textContent = "Hold to talk"; send("up"); } }
btn.addEventListener("pointerdown", press);
addEventListener("pointerup", release);
addEventListener("pointercancel", release);
setInterval(() => fetch("/voice/ptt/heartbeat", {method:"POST",
  headers:{"Content-Type":"application/json"}, body: JSON.stringify({token})}), 3000);

// ---- Duplex audio over one websocket (s16le 48 kHz mono both ways) ----
const workletSrc = `
class Pcm extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      const buf = new Int16Array(ch.length);
      for (let i = 0; i < ch.length; i++) {
        const s = Math.max(-1, Math.min(1, ch[i]));
        buf[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      this.port.postMessage(buf.buffer, [buf.buffer]);
    }
    return true;
  }
}
registerProcessor("pcm", Pcm);`;

let audioStarted = false;
let ws = null;
let nextPlayTime = 0;
let ctx = null;

async function startAudio() {
  if (audioStarted) return;
  audioStarted = true;
  try {
    ctx = new AudioContext({sampleRate: 48000});
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    await ctx.audioWorklet.addModule(
      URL.createObjectURL(new Blob([workletSrc], {type: "application/javascript"})));
    const src = ctx.createMediaStreamSource(stream);
    const node = new AudioWorkletNode(ctx, "pcm");
    src.connect(node);
    node.connect(ctx.destination);  // required for the worklet to run; mic is not audible (sent, not played)

    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/voice/page/audio?token=${encodeURIComponent(token)}`);
    ws.binaryType = "arraybuffer";
    node.port.onmessage = (ev) => {
      // The hold is the mic gate: only held audio crosses the wire.
      if (down && ws.readyState === WebSocket.OPEN) ws.send(ev.data);
    };
    ws.onmessage = (ev) => playPcm(ev.data);
    ws.onclose = () => { status.textContent = "audio disconnected"; };
  } catch (err) {
    status.textContent = "mic failed: " + err;
  }
}

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
</script></body></html>"""
