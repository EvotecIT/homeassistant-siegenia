"""Session ownership and disconnect behavior over a real local WebSocket."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from aiohttp import ClientSession, web

from custom_components.siegenia.siegenia_client.client import SiegeniaClient, SiegeniaError

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize("borrowed", [False, True])
async def test_cancelled_handshake_releases_only_owned_session(borrowed):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def handler(request):
        entered.set()
        await release.wait()
        return web.Response(status=503)

    async with local_server(handler) as port:
        supplied = ClientSession() if borrowed else None
        client = SiegeniaClient("127.0.0.1", port=port, ws_protocol="ws", session=supplied)
        connecting = asyncio.create_task(client.connect())
        session = None
        try:
            async with asyncio.timeout(5):
                await entered.wait()
                session = client._session
                assert session is not None
                connecting.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await connecting
            assert not client.connected
            assert session.closed is (not borrowed)
            assert client._session is supplied
        finally:
            release.set()
            connecting.cancel()
            await asyncio.gather(connecting, return_exceptions=True)
            await client.disconnect()
            if supplied is not None:
                await supplied.close()


@asynccontextmanager
async def local_server(handler):
    app = web.Application()
    app.router.add_get("/WebSocket", handler)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    try:
        await site.start()
        yield runner.addresses[0][1]
    finally:
        await runner.cleanup()


@pytest.mark.parametrize("borrowed", [False, True])
async def test_disconnect_fails_pending_request_and_respects_session_owner(borrowed):
    pending_received = asyncio.Event()
    commands = []

    async def handler(request):
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        async for message in websocket:
            payload = message.json()
            commands.append(payload["command"])
            if payload["command"] == "getDeviceParams":
                pending_received.set()
                continue
            await websocket.send_json({
                "id": payload["id"], "status": "ok", "data": {"serialnr": "12345"},
            })
        return websocket

    async with local_server(handler) as port:
        supplied = ClientSession() if borrowed else None
        client = SiegeniaClient("127.0.0.1", port=port, ws_protocol="ws", session=supplied)
        pending = None
        try:
            await client.connect()
            session = client._session
            assert session is not None
            await client.login("admin", "test-password")
            assert (await client.get_device())["data"]["serialnr"] == "12345"
            pending = asyncio.create_task(client.get_device_params())
            async with asyncio.timeout(5):
                await pending_received.wait()
                await client.disconnect()
                with pytest.raises(SiegeniaError, match="Connection closed"):
                    await pending
            assert not client.connected
            assert session.closed is (not borrowed)
            assert commands == ["login", "getDevice", "getDeviceParams"]
            assert not client._awaiting
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await client.disconnect()
            if supplied is not None:
                await supplied.close()


@pytest.mark.parametrize("borrowed", [False, True])
async def test_failed_handshake_releases_only_owned_session(borrowed):
    async def handler(request):
        return web.Response(status=503)

    async with local_server(handler) as port:
        supplied = ClientSession() if borrowed else None
        client = SiegeniaClient("127.0.0.1", port=port, ws_protocol="ws", session=supplied)
        try:
            from aiohttp import WSServerHandshakeError

            with pytest.raises(WSServerHandshakeError):
                await client.connect()
            assert not client.connected
            if supplied is None:
                assert client._session is None
            else:
                assert client._session is supplied
                assert not supplied.closed
        finally:
            await client.disconnect()
            if supplied is not None:
                await supplied.close()
