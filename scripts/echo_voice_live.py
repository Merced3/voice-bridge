"""Live full-duplex check over the web channel (mirror of discord-hub's
scripts/echo_voice_live.py — the stand-in consumer).

Attaches to the bridge's consumer stream and ECHOES any received audio
straight back. Open http://<host>:8200/ptt?token=... on a phone, hold the
button, speak, release — you should hear yourself. That echo proves
capture, the consumer contract, and playback at once.

Usage:
    python scripts/echo_voice_live.py [--base-url http://127.0.0.1:8200] [--owner ...]

Stop with Ctrl+C. The bridge must be running (python -m voice_bridge.main).
The consumer side of the contract is NOT token-gated (owner-gated, like
discord-hub); the page is.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

OWNER = "http://localhost:8200/echo-test"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8200")
    parser.add_argument("--owner", default=OWNER)
    args = parser.parse_args()

    ws_url = args.base_url.replace("http", "ws") + f"/voice/stream?owner={args.owner}"
    total_bytes = 0
    try:
        try:
            connect = websockets.connect(ws_url, max_size=None)
        except OSError as exc:
            print(f"cannot reach the bridge at {args.base_url} ({exc})\n"
                  "is it running?  ./.venv/Scripts/python -m voice_bridge.main")
            return
        async with connect as ws:
            print("stream attached — hold the button on the /ptt page and speak; "
                  "you should hear an echo on release")
            async for raw in ws:
                event = json.loads(raw)
                if event["type"] == "speaking":
                    print(f"speaking {event['state']}: user {event['user_id']}")
                elif event["type"] == "audio":
                    pcm = base64.b64decode(event["pcm"])
                    total_bytes += len(pcm)
                    await ws.send(pcm)  # echo back: full-duplex proof
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except (InvalidStatus, ConnectionClosed) as exc:
        print(f"stream refused: {exc}\n"
              "another consumer already holds the one stream slot — check for a\n"
              "stray echo/consumer process (or a second terminal) and stop it,\n"
              "then retry. Only one stream may be attached at a time.")
        return
    finally:
        print(f"audio bytes received: {total_bytes or '(none)'}")


if __name__ == "__main__":
    asyncio.run(main())
