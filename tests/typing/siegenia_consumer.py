"""Static-only installed client contract; this module is never executed."""

from typing import assert_type

from aiohttp import ClientSession
from siegenia_client import AuthenticationError, SiegeniaClient
from siegenia_client.client import SiegeniaClient as ModuleClient


async def read(session: ClientSession) -> bool:
    client = SiegeniaClient("127.0.0.1", session=session)
    other: ModuleClient = client
    assert_type(other.connected, bool)
    try:
        await other.login("user", "password")
        await other.open_close("one", "open")  # type: ignore[arg-type]
    except AuthenticationError:
        return False
    finally:
        await other.disconnect()
    return other.connected
