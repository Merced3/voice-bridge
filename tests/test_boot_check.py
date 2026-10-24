"""GET /boot-check: reports VOICE_BRIDGE_BOOT_TOKEN as read at module import.

The value is frozen when ``voice_bridge.boot`` is imported — changing the
env var later must not change what the route returns. Tests reload the
module under a patched environment, then restore it afterwards so other
suites are unaffected.
"""

import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import voice_bridge.boot as boot_module
from voice_bridge.room import Room


def make_client_with_env(env: dict[str, str]) -> TestClient:
    """Reload boot/api under a patched env and build a fresh app."""
    with patch.dict(os.environ, env, clear=False):
        importlib.reload(boot_module)
        import voice_bridge.api as api_module

        importlib.reload(api_module)
        return TestClient(api_module.create_api(Room(), token="test-token"))


def restore_modules() -> None:
    importlib.reload(boot_module)
    import voice_bridge.api as api_module

    importlib.reload(api_module)


class BootCheckTests(unittest.TestCase):
    def tearDown(self):
        restore_modules()

    def test_boot_check_returns_token_value_captured_at_import(self):
        client = make_client_with_env({"VOICE_BRIDGE_BOOT_TOKEN": "abc123"})
        resp = client.get("/boot-check")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["boot_token"], "abc123")

    def test_boot_check_value_is_frozen_at_import(self):
        with patch.dict(os.environ, {"VOICE_BRIDGE_BOOT_TOKEN": "A"}, clear=False):
            importlib.reload(boot_module)
            import voice_bridge.api as api_module

            importlib.reload(api_module)
            client = TestClient(api_module.create_api(Room(), token="test-token"))
        # Env is back to whatever it was (not "A") at request time.
        resp = client.get("/boot-check")
        self.assertEqual(resp.json()["boot_token"], "A")

    def test_boot_check_missing_env_var_returns_empty_string(self):
        env = os.environ.copy()
        env.pop("VOICE_BRIDGE_BOOT_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            importlib.reload(boot_module)
            import voice_bridge.api as api_module

            importlib.reload(api_module)
            client = TestClient(api_module.create_api(Room(), token="test-token"))
        resp = client.get("/boot-check")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["boot_token"], "")

    def test_boot_check_not_token_gated(self):
        client = make_client_with_env({"VOICE_BRIDGE_BOOT_TOKEN": "abc123"})
        resp = client.get("/boot-check")  # no token anywhere
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
