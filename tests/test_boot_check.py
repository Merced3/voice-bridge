"""GET /boot-check: reports VOICE_BRIDGE_BOOT_TOKEN as read at module import.

Fail-fast contract: ``voice_bridge.api`` reads the env var with square
brackets at import time, so a missing variable must crash the process
immediately (KeyError) rather than silently defaulting. The captured
value is frozen at import — changing the env var later must not change
what the route returns. Tests reload the module under a patched
environment, then restore it afterwards so other suites are unaffected.
"""

import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

# voice_bridge.api reads VOICE_BRIDGE_BOOT_TOKEN at import time (fail-fast),
# so it must be set before the module is first imported.
os.environ.setdefault("VOICE_BRIDGE_BOOT_TOKEN", "test-boot-token")

import voice_bridge.api as api_module
from voice_bridge.room import Room


def make_client_with_env(env: dict[str, str]) -> TestClient:
    """Reload api under a patched env and build a fresh app."""
    with patch.dict(os.environ, env, clear=False):
        importlib.reload(api_module)
        return TestClient(api_module.create_api(Room(), token="test-token"))


def restore_module() -> None:
    with patch.dict(
        os.environ, {"VOICE_BRIDGE_BOOT_TOKEN": "restored"}, clear=False
    ):
        importlib.reload(api_module)


class BootCheckTests(unittest.TestCase):
    def tearDown(self):
        restore_module()

    def test_boot_check_returns_token_value_captured_at_import(self):
        client = make_client_with_env({"VOICE_BRIDGE_BOOT_TOKEN": "abc123"})
        resp = client.get("/boot-check")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["boot_token"], "abc123")

    def test_boot_check_value_is_frozen_at_import(self):
        with patch.dict(os.environ, {"VOICE_BRIDGE_BOOT_TOKEN": "A"}, clear=False):
            importlib.reload(api_module)
            client = TestClient(api_module.create_api(Room(), token="test-token"))
        # Env is back to whatever it was (not "A") at request time.
        resp = client.get("/boot-check")
        self.assertEqual(resp.json()["boot_token"], "A")

    def test_boot_check_not_token_gated(self):
        client = make_client_with_env({"VOICE_BRIDGE_BOOT_TOKEN": "abc123"})
        resp = client.get("/boot-check")  # no token anywhere
        self.assertEqual(resp.status_code, 200)


class FailFastTests(unittest.TestCase):
    def tearDown(self):
        restore_module()

    def test_missing_env_var_crashes_at_import(self):
        env = os.environ.copy()
        env.pop("VOICE_BRIDGE_BOOT_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(KeyError):
                importlib.reload(api_module)


if __name__ == "__main__":
    unittest.main()
