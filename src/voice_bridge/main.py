"""Entry point: runs the bridge (web page + API) inside the
automation-harness, which owns the lifecycle — single-instance lock,
graceful shutdown, supervision with restart, structured logs, status.json.
"""

from __future__ import annotations

import asyncio
import logging
import time

import uvicorn
from automation_harness import Harness, HarnessConfig, ServiceContext

from .api import create_api
from .config import Settings
from .room import Room

logger = logging.getLogger(__name__)


async def bridge_service(ctx: ServiceContext) -> None:
    """The bridge as a harness-supervised service: runs until the harness
    requests shutdown via ctx.stop_event."""
    settings = Settings()  # type: ignore[call-arg]  # values come from env
    room = Room(heartbeat_timeout=settings.heartbeat_timeout)
    api = create_api(room, token=settings.token, started_at=time.time())
    server = uvicorn.Server(
        uvicorn.Config(api, host=settings.host, port=settings.port, log_level="info")
    )

    async def shutdown_when_asked() -> None:
        await ctx.stop_event.wait()
        logger.info("shutdown requested by harness")
        server.should_exit = True

    logger.info("Starting voice-bridge on %s:%s", settings.host, settings.port)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(server.serve())
        tg.create_task(shutdown_when_asked())


def main() -> None:
    harness = Harness(HarnessConfig(data_dir="data"), name="voice-bridge")
    harness.add_service("bridge", bridge_service)
    harness.run()  # async runtime: harness owns the event loop


if __name__ == "__main__":
    main()
