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

The owner opens `http://<host>:8200/ptt?token=...` on a phone, holds the
button, and talks; the consuming project receives exact press/release
turn boundaries and the audio between them, and streams its reply back.

See `docs/api.md` for the full contract, `docs/architecture.md` for how it
works inside, and `docs/decisions/` for the boundary decisions.

## Running it

The bridge runs inside the automation-harness (sibling repo), which owns
the lifecycle: single-instance lock, supervision with restart, graceful
shutdown, structured logs, and `data/status.json`.

```bash
pip install -e ../automation-harness   # not on PyPI; install from sibling
pip install -e .
cp .env.example .env                   # set VOICE_BRIDGE_TOKEN
python -m voice_bridge.main
```

Off-LAN access (phone away from home) is via Tailscale, never a public
tunnel.

## Live verification

With the bridge running on the LAN:

```bash
pip install -e ".[dev]"
python scripts/echo_voice_live.py
```

Then open the `/ptt` page on a phone, hold the button, speak, release —
you should hear yourself, with press/release events in the logs. That
echo is the full-duplex proof.

## Tests

Offline, no live services:

```bash
python -m unittest discover -s tests -v
```
