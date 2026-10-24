"""Deploy-gate regression tests for the boot token.

Two production rollbacks happened because the app crashed at import when
VOICE_BRIDGE_BOOT_TOKEN was unset and the deploy health gate found out
first. The contract is now fail-LOUD, not fail-dead: the service always
starts and /health always serves; /boot-check (see test_boot_check.py)
is the endpoint that reports the misconfiguration. These tests exercise
the REAL entry path (importing the entry module in a subprocess, the way
uvicorn/main.py does) so a future change cannot reintroduce an
import-time crash without going red here.
"""

import importlib
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import voice_bridge.api as api_module
from voice_bridge.room import Room


def env_without_boot_token() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("VOICE_BRIDGE_BOOT_TOKEN", None)
    return env


def restore_module() -> None:
    with patch.dict(
        os.environ, {"VOICE_BRIDGE_BOOT_TOKEN": "restored"}, clear=False
    ):
        importlib.reload(api_module)


class EntrypointAvailabilityTests(unittest.TestCase):
    def tearDown(self):
        restore_module()

    def test_entrypoint_imports_cleanly_without_boot_token(self):
        proc = subprocess.run(
            [sys.executable, "-c", "import voice_bridge.main"],
            env=env_without_boot_token(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"entrypoint must import without the boot token; stderr: {proc.stderr}",
        )

    def test_health_serves_even_without_boot_token(self):
        """The rollback guard: no boot token must never take down /health."""
        with patch.dict(os.environ, env_without_boot_token(), clear=True):
            importlib.reload(api_module)
            client = TestClient(api_module.create_api(Room(), token=""))
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_health_serves_when_boot_token_set(self):
        with patch.dict(
            os.environ, {"VOICE_BRIDGE_BOOT_TOKEN": "deploy-token"}, clear=False
        ):
            importlib.reload(api_module)
            client = TestClient(api_module.create_api(Room(), token=""))
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
