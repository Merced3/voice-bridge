# Architecture

Concept-first. Jargon only where unavoidable.

## The big picture

```
                                   ┌─────────────────────────────┐
 phone / browser  ◄── HTTP+WS ──►  │         voice-bridge        │
 (hold-to-talk page,               │                             │
  mic + speaker)                   │  room.py ── one room        │
                                   │  api.py  ── one local API   │
                                   └──────────┬──────────────────┘
                                               │  WS on localhost:8200
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
                  teaching-agent       socratic-partner      (future projects)
                  "the learner said    "attach the stream    "give me exact
                   this; say that"      and drive a debate"   turn boundaries"
```

Two faces, one process:

- **The page face** serves the hold-to-talk web page the owner opens on a
  phone. The page POSTs press/release + heartbeats and streams mic audio
  while held; it plays back whatever the consumer sends.
- **The consumer face** is a single duplex websocket (`/voice/stream`)
  that mirrors discord-hub's Stage-2 contract, so a project can swap
  transports with a config change.

`main.py` runs both faces inside the automation-harness, which owns the
lifecycle (single-instance lock, supervision, structured logs, status).

## Why this exists alongside discord-hub voice

Discord voice receive for bots is unsanctioned reverse-engineering — it
broke twice in three days from Discord-side changes (DAVE migration, then
RTP padding) — and Discord never exposes the PTT key state, so
turn-taking there is bounded by VAD guesses. A web page we own removes
both classes: no DAVE, no RTP, and the hold-to-talk button *is* the turn
boundary, delivered exactly as press/release events. Discord voice stays
in discord-hub as a second transport; consumers pick per situation.

## The room

There is exactly one room (LAN, one talker, v1). Unlike Discord there is
no channel resource to acquire, so there is no join/leave — the room
exists whenever a page is connected. What survives from discord-hub's
model is **ownership of the stream**: one consumer may attach at a time,
and a second attach is refused rather than queued. Two projects can never
fight over the owner's ear.

## Audio flow

```
page mic (s16le 48kHz mono, only while the button is held)
    → mono→stereo → {"type":"audio", pcm: base64 stereo} → consumer

press / release
    → {"type":"speaking", state: started|stopped} → consumer

consumer binary PCM (s16le 48kHz stereo)
    → stereo→mono → every connected page's playback queue
```

The mono↔stereo conversion (`audio.py`) is the *entire* per-transport
wire adaptation — browsers speak mono, discord-hub's contract speaks
stereo. Event shapes, ownership, and queue discipline are identical to
the hub's: bounded queues, drop-oldest on overload, because live audio is
a stream, not a backlog.

## Turn boundaries are exact, not inferred

The page only sends mic audio while the button is held — the hold is both
the mic gate and the turn boundary. Press/release also fire explicit
`speaking started/stopped` events, so a consumer never has to guess when
the owner finished talking. Heartbeat presence (`ptt.py`) tells the
consumer whether the button is currently in hand; what a consumer *does*
with that (e.g. falling back to VAD) is consumer policy, not bridge
policy.

## Runtime lifecycle

Long-running concerns — single-instance lock, graceful shutdown,
structured JSON logs, and a `status.json` snapshot — are provided by
embedding the owner's **automation-harness** as a dependency (the same
pattern as discord-hub). The bridge implements none of that itself.
