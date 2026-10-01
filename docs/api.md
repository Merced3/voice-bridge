# API — the transport contract for consumers

voice-bridge serves HTTP + websockets on `VOICE_BRIDGE_HOST:VOICE_BRIDGE_PORT`
(default `0.0.0.0:8200`). Everything below is the whole contract; if you
are a consuming project, you only need `/voice/stream`.

Token: `VOICE_BRIDGE_TOKEN` gates the **page** side (the phone is on the
LAN, so the page and its routes carry the token). The **consumer** side
(`/voice/stream`) is owner-gated, exactly like discord-hub — it is a
localhost surface for sibling projects.

## Consumer contract (mirrors discord-hub's Stage-2 stream)

### `WS /voice/stream?owner=<your-callback-url>`

One duplex stream per room. Attaching while another owner holds the
stream is refused (close code 1008, "a stream is already attached").
Missing `owner` is refused (1008). Disconnecting frees the slot.

**Bridge → consumer** (JSON text messages):

```json
{"type": "audio", "user_id": "page", "pcm": "<base64 s16le 48kHz stereo>", "timestamp": 1760000000.0}
{"type": "speaking", "user_id": "page", "state": "started"}
{"type": "speaking", "user_id": "page", "state": "stopped"}
```

- `audio` events carry mic PCM captured **while the button is held**.
- `speaking started/stopped` are the exact press/release edges — no VAD
  guessing on this transport.
- `user_id` is `"page"` in v1 (one page, one speaker).

**Consumer → bridge** (binary messages): raw PCM, s16le 48 kHz stereo,
played to every connected page. Send whenever you like; there is no
stream lifecycle beyond attach/detach.

### `GET /health`

`{"status": "ok", "uptime_s": ..., "pages_connected": n,
"button_connected": bool, "button_pressed": bool, "stream_owner": ...}`.
Use `button_connected` (heartbeat presence) to decide whether the
button-driven turn boundary is currently available.

## Page surface (not for consumers)

- `GET /ptt` — the hold-to-talk page. Open as
  `http://<host>:8200/ptt?token=<token>` on a phone.
- `POST /voice/ptt` — `{"state": "down"|"up", "token": ...}` → 204 / 400 / 403.
- `POST /voice/ptt/heartbeat` — `{"token": ...}` → 204 / 403.
- `WS /voice/page/audio?token=...` — the page's duplex audio socket:
  binary s16le 48 kHz mono each way (mic gated by the hold).

Consumers never call these; they are documented here so the token surface
is auditable in one place.

## Differences from discord-hub's contract (all documented in ADR 0001)

1. **No join/leave.** There is no channel to acquire; the room is the
   page's presence. Attach the stream directly.
2. **Wire format is still s16le 48 kHz stereo** toward consumers — the
   browser's mono is converted inside the bridge, so consumers are
   byte-compatible with the hub's stream.
3. **No `play_pcm`/`stop` endpoints.** On this transport playback is the
   stream; there is no second audio path to arbitrate.
