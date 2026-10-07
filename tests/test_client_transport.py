"""Session ownership and disconnect behavior over a real local WebSocket."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from aiohttp import ClientSession, web

from custom_components.siegenia.siegenia_client.client import AuthenticationError, SiegeniaClient, SiegeniaError

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


@pytest.mark.parametrize("malformed", ["not-json", "[]", '{"id":"invalid"}'])
async def test_malformed_message_does_not_drop_valid_response(malformed):
    async def handler(request):
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        async for message in websocket:
            payload = message.json()
            await websocket.send_str(malformed)
            await websocket.send_json({"id": payload["id"], "status": "ok"})
        return websocket

    async with local_server(handler) as port:
        client = SiegeniaClient("127.0.0.1", port=port, ws_protocol="ws", response_timeout=1)
        try:
            await client.connect()
            assert (await client.get_device())["status"] == "ok"
            assert client.connected
            assert not client._awaiting
        finally:
            await client.disconnect()


@pytest.mark.parametrize("status", ["device_error", "not_authenticated", "authentication_error"])
async def test_read_error_classification_preserves_connection_for_retry(status):
    async def handler(request):
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        response_status = status
        async for message in websocket:
            payload = message.json()
            await websocket.send_json({"id": payload["id"], "status": response_status})
            response_status = "ok"
        return websocket

    async with local_server(handler) as port:
        client = SiegeniaClient("127.0.0.1", port=port, ws_protocol="ws", response_timeout=1)
        try:
            await client.connect()
            error_type = SiegeniaError if status == "device_error" else AuthenticationError
            with pytest.raises(error_type, match=status) as caught:
                await client.get_device()
            assert type(caught.value) is error_type
            assert not client._awaiting
            assert client.connected
            assert (await client.get_device())["status"] == "ok"
        finally:
            await client.disconnect()


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
            async with asyncio.timeout(5):
                await client.connect()
                assert (await client.get_device())["data"]["serialnr"] == "12345"
            assert client.connected
            if borrowed:
                assert client._session is session
            else:
                assert client._session is not session
            assert not client._awaiting
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await client.disconnect()
            if supplied is not None:
                await supplied.close()


@pytest.mark.parametrize("cancel", [False, True])
async def test_abandoned_request_releases_waiter_and_late_reply_does_not_replace_next(cancel):
    received = asyncio.Event()

    async def handler(request):
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        first = None
        async for message in websocket:
            payload = message.json()
            if first is None:
                first = payload
                received.set()
                continue
            await websocket.send_json({"id": first["id"], "status": "ok", "data": "late"})
            await websocket.send_json({"id": payload["id"], "status": "ok", "data": "current"})
        return websocket

    async with local_server(handler) as port:
        client = SiegeniaClient("127.0.0.1", port=port, ws_protocol="ws", response_timeout=1)
        pending = None
        try:
            await client.connect()
            pending = asyncio.create_task(client.get_device())
            async with asyncio.timeout(5):
                await received.wait()
                if cancel:
                    pending.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await pending
                else:
                    with pytest.raises(SiegeniaError, match="Timeout waiting for response"):
                        await pending
            assert not client._awaiting
            assert client.connected
            assert (await client.get_device())["data"] == "current"
            assert not client._awaiting
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await client.disconnect()


async def test_heartbeat_survives_device_error_and_stops_on_disconnect():
    recovered = asyncio.Event()
    requests = []
    logs = []

    async def handler(request):
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        async for message in websocket:
            payload = message.json()
            requests.append(payload)
            await websocket.send_json({
                "id": payload["id"],
                "status": "device_error" if len(requests) == 1 else "ok",
            })
            if len(requests) >= 2:
                recovered.set()
        return websocket

    async with local_server(handler) as port:
        client = SiegeniaClient("127.0.0.1", port=port, ws_protocol="ws", logger=logs.append)
        try:
            await client.connect()
            await client.start_heartbeat(interval=0.01)
            heartbeat = client._hb_task
            await client.start_heartbeat(interval=0.01)
            assert client._hb_task is heartbeat
            async with asyncio.timeout(5):
                await recovered.wait()
            assert all(item["command"] == "keepAlive" for item in requests)
            assert all(item["params"] == {"extend_session": True} for item in requests)
            assert any("Heartbeat error:" in message for message in logs)
            await client.disconnect()
            assert heartbeat is not None and heartbeat.done()
            assert client._hb_task is None
            assert not client.connected
            assert not client._awaiting
        finally:
            await client.disconnect()


@pytest.mark.parametrize("borrowed", [False, True])
async def test_failed_handshake_can_retry_with_correct_session_ownership(borrowed):
    accepting = False

    async def handler(request):
        if not accepting:
            return web.Response(status=503)
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        async for message in websocket:
            payload = message.json()
            await websocket.send_json({
                "id": payload["id"], "status": "ok", "data": {"serialnr": "12345"},
            })
        return websocket

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
            accepting = True
            async with asyncio.timeout(5):
                await client.connect()
                assert (await client.get_device())["data"]["serialnr"] == "12345"
                recovered_session = client._session
                assert recovered_session is not None
                if borrowed:
                    assert recovered_session is supplied
                await client.disconnect()
            assert recovered_session.closed is (not borrowed)
            assert not client._awaiting
        finally:
            await client.disconnect()
            if supplied is not None:
                await supplied.close()
