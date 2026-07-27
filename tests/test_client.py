from __future__ import annotations

import asyncio
import json

import pytest

from custom_components.siegenia.siegenia_client.client import (
    AuthenticationError,
    SiegeniaClient,
    SiegeniaError,
)


class _ImmediateResponseWebSocket:
    def __init__(
        self,
        client: SiegeniaClient,
        response: dict[str, object],
    ) -> None:
        self._client = client
        self._response = response
        self.closed = False

    async def send_str(self, message: str) -> None:
        payload = json.loads(message)
        response = {**self._response, "id": payload["id"]}
        self._client._awaiting[payload["id"]].set_result(response)


async def test_fast_response_is_registered_before_send() -> None:
    client = SiegeniaClient("192.0.2.1")
    client._ws = _ImmediateResponseWebSocket(client, {"status": "ok"})  # type: ignore[assignment]

    response = await client.get_device()

    assert response["status"] == "ok"


async def test_login_password_is_redacted_from_debug_log() -> None:
    messages: list[str] = []
    client = SiegeniaClient("192.0.2.1", logger=messages.append)
    client._ws = _ImmediateResponseWebSocket(client, {"status": "ok"})  # type: ignore[assignment]

    await client.login("admin", "super-secret-password")

    rendered = "\n".join(messages)
    assert "super-secret-password" not in rendered
    assert '"password":"***"' in rendered


async def test_device_error_status_is_not_reported_as_success() -> None:
    client = SiegeniaClient("192.0.2.1")
    client._ws = _ImmediateResponseWebSocket(  # type: ignore[assignment]
        client,
        {"status": "device_error"},
    )

    with pytest.raises(SiegeniaError, match="device_error"):
        await client.get_device()


async def test_any_failed_login_status_is_an_authentication_error() -> None:
    client = SiegeniaClient("192.0.2.1")
    client._ws = _ImmediateResponseWebSocket(  # type: ignore[assignment]
        client,
        {"status": "invalid_credentials"},
    )

    with pytest.raises(AuthenticationError, match="invalid_credentials"):
        await client.login("admin", "wrong-password")


async def test_disconnect_waits_for_background_tasks() -> None:
    client = SiegeniaClient("192.0.2.1")

    async def _wait_forever() -> None:
        await asyncio.Event().wait()

    heartbeat_task = asyncio.create_task(_wait_forever())
    receiver_task = asyncio.create_task(_wait_forever())
    client._hb_task = heartbeat_task
    client._receiver_task = receiver_task

    class _WebSocket:
        closed = False

        async def close(self) -> None:
            self.closed = True

    websocket = _WebSocket()
    client._ws = websocket  # type: ignore[assignment]

    await client.disconnect()

    assert websocket.closed
    assert heartbeat_task.done()
    assert receiver_task.done()
