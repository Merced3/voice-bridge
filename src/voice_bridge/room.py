"""The room: page connections, the one consumer stream, event fan-out.

voice-bridge models exactly one room (LAN, one talker, v1). There is no
join/leave: unlike Discord there is no channel resource to acquire — the
room *is* the page's presence (see docs/decisions/0001). Ownership still
mirrors discord-hub: one consumer stream at a time; a second attach is
refused.

Audio flow:

- page (s16le 48 kHz mono, while the button is held)
      → stereo-converted → {"type": "audio", ...} events → consumer
- press/release → {"type": "speaking", state: started|stopped} → consumer
- consumer binary (s16le 48 kHz stereo)
      → mono-converted → every connected page's playback queue

Queues are bounded and drop-oldest on overload: live audio is a stream,
not a backlog — the same discipline as discord-hub's VoiceStream.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time

from .audio import mono_to_stereo, stereo_to_mono
from .ptt import RemotePTT

logger = logging.getLogger(__name__)

_QUEUE_MAX = 500  # ~10 s of 20 ms frames; drop oldest on overload
PAGE_USER_ID = "page"  # v1: one page, one speaker


class StreamTakenError(RuntimeError):
    """Another consumer stream is already attached to the room."""


def _put_drop_oldest(queue: asyncio.Queue, item) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        pass


class ConsumerStream:
    """The one duplex stream a consuming project attaches to the room.

    Events toward the consumer mirror discord-hub's ``/voice/stream``:
    ``{"type": "audio", "user_id", "pcm": base64 s16le 48kHz stereo,
    "timestamp"}`` and ``{"type": "speaking", "user_id", "state"}``.
    Outbound is raw bytes fed by the consumer for playback to the pages.
    """

    def __init__(self, owner: str) -> None:
        self.owner = owner
        self.events: asyncio.Queue[dict] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def _emit(self, event: dict) -> None:
        if not self._closed:
            _put_drop_oldest(self.events, event)

    def emit_audio(self, pcm_stereo: bytes) -> None:
        self._emit({
            "type": "audio",
            "user_id": PAGE_USER_ID,
            "pcm": base64.b64encode(pcm_stereo).decode("ascii"),
            "timestamp": time.time(),
        })

    def emit_speaking(self, state: str) -> None:
        self._emit({"type": "speaking", "user_id": PAGE_USER_ID, "state": state})


class Room:
    """Owns page connections and the (single) consumer stream."""

    def __init__(self, *, heartbeat_timeout: float = 6.0) -> None:
        self.ptt = RemotePTT(heartbeat_timeout_seconds=heartbeat_timeout)
        self.ptt.on_press = lambda: self._speaking("started")
        self.ptt.on_release = lambda: self._speaking("stopped")
        self._stream: ConsumerStream | None = None
        self._lock = asyncio.Lock()
        # Each connected page gets a bounded playback queue (mono s16le).
        self._pages: set[asyncio.Queue[bytes]] = set()

    # -- consumer side ----------------------------------------------------

    async def attach_stream(self, owner: str) -> ConsumerStream:
        """Attach the one allowed consumer stream to the room."""
        async with self._lock:
            if self._stream is not None and not self._stream.closed:
                raise StreamTakenError(
                    f"a stream is already attached (owner {self._stream.owner})"
                )
            self._stream = ConsumerStream(owner)
            logger.info("consumer stream attached (owner %s)", owner)
            return self._stream

    async def detach_stream(self, stream: ConsumerStream) -> None:
        async with self._lock:
            if self._stream is stream:
                stream.close()
                self._stream = None
                logger.info("consumer stream detached (owner %s)", stream.owner)

    def stream_detached(self, stream: ConsumerStream) -> None:
        """Sync variant for websocket teardown paths."""
        if self._stream is stream:
            stream.close()
            self._stream = None
            logger.info("consumer stream detached (owner %s)", stream.owner)

    def _speaking(self, state: str) -> None:
        if self._stream is not None:
            self._stream.emit_speaking(state)

    # -- page side --------------------------------------------------------

    def add_page(self, queue: asyncio.Queue[bytes]) -> None:
        self._pages.add(queue)
        logger.info("page connected (%d total)", len(self._pages))

    def remove_page(self, queue: asyncio.Queue[bytes]) -> None:
        self._pages.discard(queue)
        logger.info("page disconnected (%d total)", len(self._pages))

    def page_audio(self, pcm_mono: bytes) -> None:
        """Mic audio from a page (held button only) → consumer event."""
        if self._stream is not None:
            self._stream.emit_audio(mono_to_stereo(pcm_mono))

    def consumer_audio(self, pcm_stereo: bytes) -> None:
        """Playback audio from the consumer → every page (mono)."""
        if not self._pages:
            return
        mono = stereo_to_mono(pcm_stereo)
        for queue in self._pages:
            _put_drop_oldest(queue, mono)

    # -- status ------------------------------------------------------------

    def status(self) -> dict:
        return {
            "pages_connected": len(self._pages),
            "button_connected": self.ptt.connected,
            "button_pressed": self.ptt.pressed,
            "stream_owner": self._stream.owner if self._stream is not None else None,
        }
