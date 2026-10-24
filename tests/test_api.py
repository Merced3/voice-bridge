"""HTTP surface: token gating, PTT routes, health. Offline (TestClient)."""

import os
import unittest

# voice_bridge.api reads VOICE_BRIDGE_BOOT_TOKEN at import time (fail-fast),
# so it must be set before the module is first imported.
os.environ.setdefault("VOICE_BRIDGE_BOOT_TOKEN", "test-boot-token")

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from voice_bridge.api import create_api
from voice_bridge.room import Room

TOKEN = "test-token"


def make_client(token: str = TOKEN) -> TestClient:
    return TestClient(create_api(Room(), token=token))


class TokenGatingTests(unittest.TestCase):
    def test_ptt_rejected_without_token(self):
        client = make_client()
        resp = client.post("/voice/ptt", json={"state": "down"})
        self.assertEqual(resp.status_code, 403)

    def test_heartbeat_rejected_with_wrong_token(self):
        client = make_client()
        resp = client.post("/voice/ptt/heartbeat", json={"token": "wrong"})
        self.assertEqual(resp.status_code, 403)

    def test_empty_configured_token_trusts_lan(self):
        client = make_client(token="")
        resp = client.post("/voice/ptt", json={"state": "down"})
        self.assertEqual(resp.status_code, 204)


class PttRouteTests(unittest.TestCase):
    def test_press_release_drive_room_state(self):
        room = Room()
        client = TestClient(create_api(room, token=TOKEN))
        resp = client.post("/voice/ptt", json={"state": "down", "token": TOKEN})
        self.assertEqual(resp.status_code, 204)
        self.assertTrue(room.ptt.pressed)
        self.assertTrue(room.ptt.connected)
        client.post("/voice/ptt", json={"state": "up", "token": TOKEN})
        self.assertFalse(room.ptt.pressed)

    def test_bad_state_is_400(self):
        client = make_client()
        resp = client.post("/voice/ptt", json={"state": "sideways", "token": TOKEN})
        self.assertEqual(resp.status_code, 400)

    def test_heartbeat_marks_presence(self):
        room = Room()
        client = TestClient(create_api(room, token=TOKEN))
        self.assertFalse(room.ptt.connected)
        resp = client.post("/voice/ptt/heartbeat", json={"token": TOKEN})
        self.assertEqual(resp.status_code, 204)
        self.assertTrue(room.ptt.connected)


class SurfaceTests(unittest.TestCase):
    def test_ptt_page_served(self):
        client = make_client()
        resp = client.get("/ptt")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Hold to talk", resp.text)

    def test_health_reports_room_status(self):
        client = make_client()
        body = client.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("pages_connected", body)
        self.assertIn("button_pressed", body)


class WebsocketTests(unittest.TestCase):
    def test_page_audio_rejected_without_token(self):
        client = make_client()
        with (
            self.assertRaises(WebSocketDisconnect),
            client.websocket_connect("/voice/page/audio?token=wrong"),
        ):
            pass

    def test_stream_requires_owner(self):
        client = make_client()
        with (
            self.assertRaises(WebSocketDisconnect),
            client.websocket_connect("/voice/stream"),
        ):
            pass

    def test_second_stream_refused(self):
        client = make_client()
        with (
            client.websocket_connect("/voice/stream?owner=a"),
            self.assertRaises(WebSocketDisconnect),
            client.websocket_connect("/voice/stream?owner=b"),
        ):
            pass

    def test_full_duplex_over_websockets(self):
        """Page mic → consumer event; consumer PCM → page playback."""
        client = make_client()
        with (
            client.websocket_connect("/voice/stream?owner=a") as stream,
            client.websocket_connect(f"/voice/page/audio?token={TOKEN}") as page,
        ):
            page.send_bytes(b"\x01\x00\x02\x00")  # two mono samples
            event = stream.receive_json()
            self.assertEqual(event["type"], "audio")
            stream.send_bytes(b"\x05\x00\x05\x00")  # one stereo frame
            self.assertEqual(page.receive_bytes(), b"\x05\x00")


if __name__ == "__main__":
    unittest.main()


class VersionRouteTests(unittest.TestCase):
    def test_version_returns_200_with_version_field(self):
        client = make_client()
        resp = client.get("/version")
        self.assertEqual(resp.status_code, 200)
        version = resp.json().get("version")
        self.assertIsInstance(version, str)
        self.assertTrue(version)

    def test_version_matches_installed_package_metadata(self):
        from importlib.metadata import version as pkg_version

        client = make_client()
        resp = client.get("/version")
        self.assertEqual(resp.json()["version"], pkg_version("voice-bridge"))

    def test_version_needs_no_token(self):
        client = make_client()  # token configured, none supplied on request
        resp = client.get("/version")
        self.assertEqual(resp.status_code, 200)
