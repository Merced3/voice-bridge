"""GET /boot-check: reports VOICE_BRIDGE_BOOT_TOKEN as read at module import.

Fail-loud contract (after two production rollbacks from fail-fast): the
service ALWAYS starts, with or without the variable — availability of
voice beats a diagnostic. But the misconfiguration is machine-detectable:
/boot-check answers 503 when the token was unset at import, 200 with the
captured value otherwise. The value is frozen at import — changing the
env var later must not change what the route returns. Tests reload the
module under a patched environment, then restore it afterwards so other
suites are unaffected.
"""

import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import voice_bridge.api as api_module
from voice_bridge.room import Room


def make_client_with_env(env: dict[str, str]) -> TestClient:
    """Reload api under a patched env and build a fresh app."""
    with patch.dict(os.environ, env, clear=False):
        importlib.reload(api_module)
        return TestClient(api_module.create_api(Room(), token="test-token"))


def env_without_boot_token() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("VOICE_BRIDGE_BOOT_TOKEN", None)
    return env


def restore_module() -> None:
    with patch.dict(
        os.environ, {"VOICE_BRIDGE_BOOT_TOKEN": "restored"}, clear=False
    ):
        importlib.reload(api_module)


class BootCheckTests(unittest.TestCase):
    def tearDown(self):
        restore_module()

    def test_boot_check_returns_token_when_set(self):
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

    def test_boot_check_returns_503_when_token_unset(self):
        with patch.dict(os.environ, env_without_boot_token(), clear=True):
            importlib.reload(api_module)
            client = TestClient(api_module.create_api(Room(), token="test-token"))
        resp = client.get("/boot-check")
        self.assertEqual(resp.status_code, 503)


if __name__ == "__main__":
    unittest.main()
