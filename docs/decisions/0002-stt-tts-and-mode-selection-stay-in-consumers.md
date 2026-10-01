# ADR 0002 — STT/TTS and turn-taking mode selection stay in consumers

Date: 2026-10-02

## Context

After the founding milestone, the owner asked the obvious question:
teaching-agent already has working Deepgram STT / ElevenLabs TTS
plumbing, socratic-partner will likely want voice one day, and STT/TTS
feels like "dumb" machinery — so why not put it in voice-bridge now
instead of paying for it twice? Same question for teaching-agent's
dual-mode turn-taking (manual button mode vs. automatic VAD fallback).

This ADR records the reasoning so future sessions don't re-litigate it
from scratch.

## Decision

**STT/TTS stays in teaching-agent until a second real voice project
exists; if it is ever shared, it becomes a separate consumer-side
package — never part of voice-bridge. Turn-taking mode selection stays
in consumers permanently.**

### Why STT/TTS is not "dumb"

Transport is dumb because it has zero choices: PCM in, PCM out, button
events. STT/TTS is all choices, and teaching-agent's implementation is
opinionated about every one:

- Deepgram **endpointing draws utterance boundaries** — that is
  turn-taking policy (plus `finalize()` on PTT release, plus endpointing
  as the non-PTT fallback).
- ElevenLabs **voice selection is persona** — Alvar's voice is part of
  teaching-agent's identity; another project wants a different voice,
  maybe a different provider and latency/cost tradeoff.
- The **spoken-turn wrapper** (1–3 sentences, no tools) and the **"Mm."
  fillers** are pedagogy.

Extracting today means either parameterizing every knob (an abstraction
boundary guessed from one data point) or baking in teaching's choices
(a policy leak, forbidden by `../../PRINCIPLES.md` #1). The trigger for
extraction is a second *real* need — e.g. a concrete socratic-partner
voice milestone — at which point the generic-vs-specific boundary is
measured, not guessed. Extraction later is cheap because
teaching-agent's `voice/` is already modular (`stt.py`, `tts.py` as
separate files): it is a move, not a rewrite.

### Why never inside voice-bridge

The moment the bridge does STT, its contract stops being "PCM in, PCM
out" and becomes "PCM in, text out" — it no longer mirrors discord-hub's
`/voice/stream`, and swap-transports-with-a-config-change (ADR 0001)
dies. If STT/TTS is shared, it lives in a layer *between* brain and
transport that both consumers import.

### Why mode selection is consumer policy

The transport facts already live in voice-bridge: heartbeat presence
(`button_connected` in `/health`), exact press/release edges, and
`speaking started/stopped` events. What lives in teaching-agent is the
*selection*: "when the button lapses, fall back to VAD + grace." That is
a policy choice — another consumer might refuse to run without the
button, or pause the session. The bridge exposes exact signals; the
consumer decides what they mean.

## Consequences

- When a second real voice project lands, that session extracts
  `stt.py`/`tts.py` into a shared consumer-side package with knobs
  measured from two actual consumers. voice-bridge's contract does not
  change.
- voice-bridge may add transport-level signals in the future (e.g. a
  continuous-mic page mode), but it must never interpret them into
  conversation decisions.
- If this reasoning ever stops holding (e.g. three consumers all
  configure STT identically), revisit this ADR with the evidence.
