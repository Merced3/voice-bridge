"""Remote push-to-talk: an exact, out-of-band turn boundary.

Moved here from teaching-agent and made fully agnostic. A hold-to-talk
button we own (a phone web page today, a BLE remote later) POSTs
press/release, and this object is the shared state between that HTTP
surface and whatever consumes the events.

Presence is heartbeat-based: while heartbeats are fresh the button is "in
hand" (``connected``); when they lapse it is gone. The device being there
IS the signal — there is no mode setting, and no opinion here about what
a consumer should do when presence lapses (that is consumer policy).
"""

from __future__ import annotations

import time
from collections.abc import Callable


class RemotePTT:
    def __init__(self, *, heartbeat_timeout_seconds: float = 6.0) -> None:
        self._heartbeat_timeout = heartbeat_timeout_seconds
        self._last_heartbeat: float | None = None
        self._pressed = False
        # Wired by the room; no-ops until a consumer stream is attached.
        self.on_press: Callable[[], None] = lambda: None
        self.on_release: Callable[[], None] = lambda: None

    @property
    def connected(self) -> bool:
        """A heartbeat within the timeout means the button is in hand."""
        return self._last_heartbeat is not None and (
            time.monotonic() - self._last_heartbeat < self._heartbeat_timeout
        )

    @property
    def pressed(self) -> bool:
        return self._pressed

    def heartbeat(self) -> None:
        self._last_heartbeat = time.monotonic()

    def press(self) -> None:
        self.heartbeat()
        if not self._pressed:
            self._pressed = True
            self.on_press()

    def release(self) -> None:
        self.heartbeat()
        if self._pressed:
            self._pressed = False
            self.on_release()
