"""Minimal standalone example for the reusable Siegenia client package."""

from __future__ import annotations

import asyncio
import os

from siegenia_client import SiegeniaClient


async def main() -> None:
    host = os.environ.get("SIEGENIA_HOST", "192.168.1.30")
    user = os.environ.get("SIEGENIA_USER", "admin")
    password = os.environ.get("SIEGENIA_PASSWORD", "secret")

    client = SiegeniaClient(host)
    await client.connect()
    try:
        await client.login(user, password)
        device = await client.get_device()
        print(device)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
