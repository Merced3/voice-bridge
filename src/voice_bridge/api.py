"""The FastAPI app: the phone page, the PTT routes, and two websockets.

- ``GET /ptt`` — the hold-to-talk page (browser/phone).
- ``POST /voice/ptt`` + ``POST /voice/ptt/heartbeat`` — press/release and
  presence, token-gated (moved here from teaching-agent, agnostic).
- ``WS /voice/page/audio?token=`` — the page's duplex audio: binary s16le
  48 kHz mono each way.
- ``WS /voice/stream?owner=`` — the consumer contract, mirroring
  discord-hub's Stage-2 stream: JSON audio/speaking events toward the
  consumer (pcm = base64 s16le 48 kHz stereo), binary PCM back for
  playback. One stream at a time; a second attach is refused.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from .page import PTT_PAGE
from .room import Room, StreamTakenError

logger = logging.getLogger(__name__)


def create_api(room: Room, *, token: str = "", started_at: float | None = None) -> FastAPI:
    app = FastAPI(title="voice-bridge")
    started = started_at if started_at is not None else time.time()

    def _authorized(payload: dict[str, Any]) -> bool:
        # Empty configured token = local-only trust; set one before the
        # button leaves the LAN (Tailscale).
        return not token or payload.get("token") == token

    def _authorized_ws(websocket: WebSocket) -> bool:
        return not token or websocket.query_params.get("token") == token

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "uptime_s": round(time.time() - started, 1), **room.status()}

    @app.get("/ptt", response_class=HTMLResponse)
    async def ptt_page() -> HTMLResponse:
        return HTMLResponse(PTT_PAGE)

    @app.post("/voice/ptt")
    async def ptt_event(request: Request) -> Response:
        payload = await request.json()
        if not _authorized(payload):
            return Response(status_code=403)
        state = payload.get("state")
        if state == "down":
            room.ptt.press()
        elif state == "up":
            room.ptt.release()
        else:
            return Response(status_code=400)
        return Response(status_code=204)

    @app.post("/voice/ptt/heartbeat")
    async def ptt_heartbeat(request: Request) -> Response:
        payload = await request.json()
        if not _authorized(payload):
            return Response(status_code=403)
        room.ptt.heartbeat()
        return Response(status_code=204)

    @app.websocket("/voice/page/audio")
    async def page_audio(websocket: WebSocket) -> None:
        """The page's duplex audio socket: binary s16le 48 kHz mono both ways."""
        if not _authorized_ws(websocket):
            await websocket.close(code=1008, reason="invalid token")
            return
        await websocket.accept()
        playback: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)
        room.add_page(playback)

        async def forward_playback() -> None:
            while True:
                chunk = await playback.get()
                await websocket.send_bytes(chunk)

        async def receive_mic() -> None:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    raise WebSocketDisconnect
                data = message.get("bytes")
                if data:
                    room.page_audio(data)

        forwarder = asyncio.create_task(forward_playback())
        try:
            await receive_mic()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            forwarder.cancel()
            room.remove_page(playback)

    @app.websocket("/voice/stream")
    async def voice_stream(websocket: WebSocket) -> None:
        """Consumer duplex stream (mirrors discord-hub's /voice/stream).

        Bridge -> consumer: JSON messages, either
          {"type": "audio", "user_id": str, "pcm": base64 s16le 48kHz stereo,
           "timestamp": float}
          {"type": "speaking", "user_id": str, "state": "started"|"stopped"}
        Consumer -> bridge: binary messages of raw PCM s16le 48kHz stereo,
        played to every connected page. One stream per room; a second
        attach is refused.
        """
        owner = websocket.query_params.get("owner")
        if not owner:
            await websocket.close(code=1008, reason="owner query parameter required")
            return
        try:
            stream = await room.attach_stream(owner)
        except StreamTakenError:
            await websocket.close(code=1008, reason="a stream is already attached")
            return

        await websocket.accept()

        async def forward_events() -> None:
            while True:
                event = await stream.events.get()
                await websocket.send_json(event)

        async def receive_audio() -> None:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    raise WebSocketDisconnect
                data = message.get("bytes")
                if data:
                    room.consumer_audio(data)

        forwarder = asyncio.create_task(forward_events())
        try:
            await receive_audio()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            forwarder.cancel()
            room.stream_detached(stream)

    return app
