"""Settings for voice-bridge, loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="VOICE_BRIDGE_"
    )

    # Token gating the phone page and both websockets. Empty = local-only
    # trust; set one before the page leaves the LAN (Tailscale for off-LAN).
    token: str = ""
    host: str = "0.0.0.0"
    port: int = 8200
    heartbeat_timeout: float = 6.0
    data_dir: Path = Path("data")
