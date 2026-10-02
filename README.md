# voice-bridge

**One web page. One duplex audio channel. Every project talks voice through this.**

## Why this exists (the thesis)

Some projects need live voice conversations with the owner — the Teaching
Agent holds spoken tutoring sessions, and more will come. The first
transport was Discord voice via discord-hub, but Discord voice receive for
bots is unsanctioned reverse-engineering: it broke twice in three days
from Discord-side changes (the DAVE migration, then RTP padding), and
Discord exposes no push-to-talk key state, so turn-taking there is bounded
by VAD guesses.

A phone/browser web page removes both classes of problem entirely: no
DAVE, no RTP, and a hold-to-talk button gives *exact* turn boundaries
instead of inferred ones. voice-bridge is that channel, built once for
every project, exactly like discord-hub is the Discord channel for every
project. Discord voice in discord-hub **stays** as a second transport;
consumers pick per situation.

## The one rule that keeps this clean

**voice-bridge is transport only. It knows audio and buttons, not
conversations.**

PCM/audio in, audio out, press/release and speaking events. No STT, no
TTS, no LLM, no notion of a "learner" or a "session" — the brain is what
makes a consuming project *that* agent, and it lives in the consumer.
Consumers stay web-agnostic: they never see a websocket frame, only the
same duplex-stream contract discord-hub exposes (`/voice/stream`), so
swapping transports is a config change, not a rewrite.

## How other projects use it

The bridge runs on the local machine and exposes a small HTTP/WS API
(`0.0.0.0:8200` by default, token-gated):

- `GET /ptt` — the phone page: hold-to-talk button, heartbeat presence,
  live mic/speaker audio
- `WS /voice/stream?owner=...` — the consumer contract: per-speaker PCM +
  speaking events toward the consumer, binary PCM back for playback
  (mirrors discord-hub's Stage-2 stream)

The owner opens the `/ptt` page on a phone (HTTPS required for the mic �
`tailscale serve --bg 8200`, then `https://<pc>.<tailnet>.ts.net/ptt?token=...`;
browsers block `getUserMedia` on plain-HTTP LAN URLs), picks push-to-talk
or voice-activity mode, and talks; the consuming project receives exact press/release
turn boundaries and the audio between them, and streams its reply back.

See `docs/api.md` for the full contract, `docs/architecture.md` for how it
works inside, and `docs/decisions/` for the boundary decisions.

## Running it

The bridge runs inside the automation-harness (sibling repo), which owns
the lifecycle: single-instance lock, supervision with restart, graceful
shutdown, structured logs, and `data/status.json`.

```bash
python -m venv .venv                 # like every sibling repo, deps live in .venv
./.venv/Scripts/pip install -e ../automation-harness   # not on PyPI; install from sibling
./.venv/Scripts/pip install -e ".[dev]"
cp .env.example .env                 # set VOICE_BRIDGE_TOKEN
```

Then, always with the venv's interpreter:

```bash
./.venv/Scripts/python -m voice_bridge.main        # run the bridge
./.venv/Scripts/python -m unittest discover -s tests -v
./.venv/Scripts/python scripts/echo_voice_live.py  # live echo check
```

Off-LAN access (phone away from home) is via Tailscale, never a public
tunnel.

## Live verification

Three moving parts, all at once:

1. **The bridge** (terminal 1, leave running):
   `./.venv/Scripts/python -m voice_bridge.main`
2. **The echo consumer** (terminal 2) — a stand-in *client* that attaches
   to the running bridge and echoes audio back; it does nothing on its
   own: `./.venv/Scripts/python scripts/echo_voice_live.py`
   (you should see `stream attached — …`)
3. **The phone page** — open `http://<lan-ip>:8200/ptt?token=…`

Then hold the button, speak, release — you should hear yourself, with
press/release events in the logs. That echo is the full-duplex proof.

If the echo script is refused immediately ("stream refused"), another
consumer already holds the one stream slot — usually a stray
echo/consumer process from an earlier run. Stop it (or restart the
bridge) and retry; only one stream may be attached at a time.

## Tests

Offline, no live services:

```bash
python -m unittest discover -s tests -v
```
