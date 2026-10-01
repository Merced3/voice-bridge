# ADR 0001 — voice-bridge is transport-only, mirrors the hub contract

Date: 2026-10-02 (founding decision)

## Context

Discord voice receive for bots is unsanctioned reverse-engineering and
broke twice in three days from Discord-side changes (DAVE migration, then
RTP padding — see teaching-agent's decision log 2026-09-29 through
2026-10-01 night). Discord also exposes no PTT key state, so turn-taking
there is bounded by VAD guesses. We need a voice channel that removes
both classes of problem.

## Decision

voice-bridge is a **transport-only** helper: a token-gated phone/browser
page (hold-to-talk + duplex audio) exposing the **same consumer contract
as discord-hub's `/voice/stream`** — per-speaker PCM + speaking events
toward the consumer, binary PCM back for playback, one owned stream at a
time.

Boundary decisions, all deliberate:

1. **No brain.** No STT, no TTS, no LLM, no conversation policy, no
   "learner", no transcripts. The brain is what makes a consuming project
   *that* agent. STT/TTS extraction is deferred until a second real voice
   project proves what to extract (the "second real need" rule in
   `../../PRINCIPLES.md`); teaching-agent's working Deepgram/ElevenLabs
   plumbing stays in teaching-agent until then.
2. **No Discord code, ever.** Discord voice remains available in
   discord-hub as a second transport; consumers pick per situation via
   config.
3. **LAN first, token-gated.** Empty token = local-only trust (precedent:
   teaching-agent's `TEACHING_AGENT_VOICE_PTT_TOKEN`). Off-LAN is
   Tailscale, never a public tunnel.
4. **No join/leave.** Unlike Discord there is no channel resource to
   acquire; the room is the page's presence. Stream ownership (one
   consumer at a time, refused second attach) is preserved.
5. **Wire adaptation is mono↔stereo only.** Browsers speak s16le 48 kHz
   mono; the consumer contract stays s16le 48 kHz stereo so consumers are
   byte-compatible with the hub's stream. This is the sanctioned kind of
   per-transport deviation: the event/ownership shape still mirrors.
6. **The hold is the mic gate AND the turn boundary.** The page sends mic
   audio only while held, and press/release fire explicit
   `speaking started/stopped` events. No VAD on this transport.

## Consequences

- Consumers swap transports (Discord voice ↔ web channel) with a config
  change, not a rewrite.
- Anything that smells like meaning (turn-taking policy, endpointing,
  fillers, interruption rules) is consumer code and must not be added
  here.
- Migrating teaching-agent onto this transport is a teaching-agent
  session, not a voice-bridge one.
