"""Boot-time diagnostics: the token the process actually started with.

``BOOT_TOKEN`` is captured at module import time, so ``GET /boot-check``
reports the value the process booted with even if the environment
changes later.
"""

import os

BOOT_TOKEN = os.environ.get("VOICE_BRIDGE_BOOT_TOKEN", "")
