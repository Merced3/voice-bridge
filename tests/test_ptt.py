"""RemotePTT semantics: heartbeat presence, exact press/release edges."""

import time
import unittest
from unittest.mock import patch

from voice_bridge.ptt import RemotePTT


class PresenceTests(unittest.TestCase):
    def test_disconnected_until_first_heartbeat(self):
        ptt = RemotePTT(heartbeat_timeout_seconds=6.0)
        self.assertFalse(ptt.connected)

    def test_connected_after_heartbeat(self):
        ptt = RemotePTT(heartbeat_timeout_seconds=6.0)
        ptt.heartbeat()
        self.assertTrue(ptt.connected)

    def test_presence_lapses_after_timeout(self):
        with patch("voice_bridge.ptt.time.monotonic") as clock:
            clock.return_value = 100.0
            ptt = RemotePTT(heartbeat_timeout_seconds=6.0)
            ptt.heartbeat()
            self.assertTrue(ptt.connected)
            clock.return_value = 105.9
            self.assertTrue(ptt.connected)
            clock.return_value = 106.1
            self.assertFalse(ptt.connected)


class EdgeTests(unittest.TestCase):
    def test_press_release_fire_once_per_edge(self):
        ptt = RemotePTT()
        events = []
        ptt.on_press = lambda: events.append("press")
        ptt.on_release = lambda: events.append("release")
        ptt.press()
        ptt.press()  # held — no duplicate
        ptt.release()
        ptt.release()  # already up — no duplicate
        self.assertEqual(events, ["press", "release"])

    def test_state_flags(self):
        ptt = RemotePTT()
        self.assertFalse(ptt.pressed)
        ptt.press()
        self.assertTrue(ptt.pressed)
        ptt.release()
        self.assertFalse(ptt.pressed)

    def test_press_and_release_count_as_heartbeat(self):
        ptt = RemotePTT(heartbeat_timeout_seconds=6.0)
        ptt.press()
        self.assertTrue(ptt.connected)
        ptt.release()
        self.assertTrue(ptt.connected)

    def test_callbacks_are_noops_by_default(self):
        ptt = RemotePTT()
        ptt.press()
        ptt.release()  # must not raise


if __name__ == "__main__":
    unittest.main()
