# AGENTS.md — orientation for AI sessions

You are working on **voice-bridge**, a transport-only voice channel: a
token-gated phone/browser web page (hold-to-talk + duplex audio) that any
project can drive as its voice surface. It is a sibling of discord-hub
(same helper-project pattern) and contains **no** brain, **no** STT/TTS,
and **no** Discord code.

Read `../PRINCIPLES.md` first — the cross-project rules apply here.

## Non-negotiable design principles

1. **Transport only.** PCM/audio in, audio out, press/release (or
   speaking) events. Nothing that makes a project *that* agent belongs
   here: no STT, no TTS, no LLM, no conversation policy, no "learner",
   no transcripts. If a change gives the bridge an opinion about the
   conversation, the change is wrong.
2. **Mirror discord-hub's `/voice/stream` contract.** Consumers must be
   able to swap transports (Discord voice ↔ this web channel) with a
   config change, not a rewrite. Deviate only with a documented reason in
   `docs/decisions/` (e.g. browser wire formats are a per-transport
   detail; the event/ownership shape still mirrors).
3. **Projects stay web-agnostic.** If a change would require a consuming
   project to know what a websocket frame or an AudioWorklet is, the
   change is wrong. The consumer sees JSON events and binary PCM.
4. **Extract on the second real need.** Shared machinery (e.g. STT/TTS
   plumbing) is extracted here only when a second real voice project
   proves what to extract — not before (see `../PRINCIPLES.md` #3).
5. **Harness-embedded, not harness-supervised.** The bridge installs the
   owner's automation-harness as a dependency and lets it own the
   long-running concerns: single-instance lock, graceful shutdown,
   structured logs, status snapshots. The bridge must not re-implement
   those itself.

## Tech stack

- Python 3.13+, FastAPI + uvicorn for the local API and the web page,
  `automation-harness` (sibling repo) for runtime lifecycle.
- Config via environment variables (see `.env.example`). Token comes from
  env, never from code or docs.
- The phone page is dependency-free vanilla JS (getUserMedia +
  AudioWorklet, s16le PCM over websocket). No build step, ever.

## Where things live

- `src/voice_bridge/api.py` — the FastAPI app: page routes, PTT routes,
  the page audio websocket, the consumer `/voice/stream` websocket
- `src/voice_bridge/room.py` — the room: page connections, the one
  consumer stream, queue discipline, event fan-out
- `src/voice_bridge/ptt.py` — press/release + heartbeat presence state
  (moved here from teaching-agent, de-teaching-agent-ified)
- `src/voice_bridge/audio.py` — s16le mono↔stereo conversion (browser
  wire format ↔ discord-hub-compatible consumer wire format)
- `src/voice_bridge/page.py` — the hold-to-talk phone page (inline HTML/JS)
- `src/voice_bridge/config.py` — settings from environment
- `src/voice_bridge/main.py` — wires the API into the harness, entry point
- `scripts/echo_voice_live.py` — stand-in consumer that echoes audio back;
  the live full-duplex gate (mirror of discord-hub's echo script)
- `docs/architecture.md` — how it works, concept-first
- `docs/api.md` — the transport contract for consuming projects. Update it
  whenever the contract changes.
- `docs/decisions/` — dated boundary decisions (ADR-style)
- `tests/` — offline `unittest` suites; run with
  `python -m unittest discover -s tests -v`

## Repository boundaries

Only edit voice-bridge in this session. The sibling repos (discord-hub,
teaching-agent, socratic-partner, automation-harness) are read-only
requirements sources. Do not start live services or open microphones as
part of automated tests.

## When picking up a new task

Read `README.md` first (the thesis), then `docs/decisions/` (current
boundaries), then the module you're changing.
