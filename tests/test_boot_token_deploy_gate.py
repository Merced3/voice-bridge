"""Deploy-gate regression tests for the fail-fast boot token.

The 2026 deploy rollback happened because production started without
VOICE_BRIDGE_BOOT_TOKEN and the app crashed at import — correctly, per
the fail-fast contract, but the deploy gate discovered it first. These
tests exercise the REAL entry path (importing the entry module in a
subprocess, the way uvicorn/main.py does) so the crash mode is pinned:
fast, non-zero exit, and an error message that names the missing
variable.
"""

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("VOICE_BRIDGE_BOOT_TOKEN", "test-boot-token")

from voice_bridge.api import create_api
from voice_bridge.room import Room


def env_without_boot_token() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("VOICE_BRIDGE_BOOT_TOKEN", None)
    return env


class EntrypointCrashTests(unittest.TestCase):
    def test_entrypoint_refuses_to_start_without_boot_token(self):
        proc = subprocess.run(
            [sys.executable, "-c", "import voice_bridge.main"],
            env=env_without_boot_token(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("VOICE_BRIDGE_BOOT_TOKEN", proc.stderr)


class HealthWithTokenTests(unittest.TestCase):
    def test_health_serves_when_boot_token_set(self):
        with patch.dict(
            os.environ, {"VOICE_BRIDGE_BOOT_TOKEN": "deploy-token"}, clear=False
        ):
            client = TestClient(create_api(Room(), token=""))
            resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
