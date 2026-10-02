# 0003 — Input mode lives in the page (push-to-talk or voice activity)

Date: 2026-10-08

## Context

Discord clients offer two input modes: push-to-talk and voice activity.
The bridge's page is the equivalent of the Discord client — it is the
input device. The owner wanted the same choice on the phone, plus visible
proof the mic is actually hearing them (Discord's green ring).

## Decision

The page owns the input mode. A level gate in the page (RMS over mic
frames, ~0.8 s hangover) opens on speech and closes on silence; the gate
edges POST the exact same `/voice/ptt` down/up as the physical hold.
The bridge server and consumers see identical event streams either way —
no mode exists above the page.

The "hearing you" indicator is decoupled from the modes: a meter measures
mic level continuously, the gate decides transmission, and the ring shows
gate && level. Mode changes never touch the meter.

## Why not server-side VAD

Transport-only (ADR 0001) and no policy in helpers (PRINCIPLES #1): VAD
thresholds, hangover, and what counts as "a turn" are exactly the kind of
opinion the bridge must not grow. The page is already a special client
(like Discord's); client-side input modes keep the server a dumb pipe.
Consumers keep their exact-edge contract and their own turn policy —
in voice-activity mode the edges are just noisier, same as Discord's.

## Consequences

- `getUserMedia` needs a secure context: plain-HTTP LAN URLs load the
  page but the mic is silently blocked (iOS Safari especially). The page
  now detects this and says so; docs point at `tailscale serve` for
  HTTPS (which also covers off-LAN, per the cross-project rules).
- First real-world failure (2026-10-08) was exactly this: heartbeats
  arrived, audio socket never connected, `pages_connected: 0`.

## Live verification (2026-10-08)

First real conversation held from an iPhone over Tailscale HTTPS:
push-to-talk edges, green ring live, replies heard. The plain-HTTP mic
block was the final blocker; `tailscale serve` + the resume fix solved it.
