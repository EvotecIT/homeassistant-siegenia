from __future__ import annotations

import asyncio
import json
import ssl
from collections.abc import Mapping
from typing import Any, Callable

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType


class SiegeniaError(Exception):
    pass


class AuthenticationError(SiegeniaError):
    pass


class SiegeniaClient:
    """Async WebSocket client for Siegenia devices (MHS family)."""

    def __init__(
        self,
        host: str,
        *,
        port: int = 443,
        ws_protocol: str = "wss",
        session: ClientSession | None = None,
        logger: Callable[[str], None] | None = None,
        response_timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._ws_protocol = ws_protocol
        self._session = session
        self._own_session = False
        self._logger = logger or (lambda s: None)
        self._response_timeout = response_timeout

        self._ws: ClientWebSocketResponse | None = None
        self._req_id = 1
        self._awaiting: dict[int, asyncio.Future] = {}
        self._hb_task: asyncio.Task | None = None
        self._connected_evt = asyncio.Event()
        self._on_push: Callable[[dict[str, Any]], None] | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    async def connect(self) -> None:
        if self.connected:
            return

        if self._session is None:
            self._session = ClientSession()
            self._own_session = True

        # Accept self-signed cert on device without loading default certs
        # Avoid ssl.create_default_context() to prevent blocking certificate path loads in the event loop
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        url = f"{self._ws_protocol}://{self._host}:{self._port}/WebSocket"
        headers = {"Origin": f"{self._ws_protocol}://{self._host}:{self._port}"}
        self._ws = await self._session.ws_connect(url, ssl=ssl_ctx, headers=headers)
        self._connected_evt.set()
        asyncio.create_task(self._receiver_loop())

    async def disconnect(self) -> None:
        if self._hb_task:
            self._hb_task.cancel()
            self._hb_task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        if self._own_session and self._session:
            await self._session.close()
            self._session = None
            self._own_session = False

    async def _receiver_loop(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except Exception as exc:  # noqa: BLE001
                        self._logger(f"Failed to parse message: {exc}")
                        continue
                    req_id = data.get("id")
                    # Route to waiter if matching id
                    fut = self._awaiting.pop(int(req_id), None) if req_id is not None else None
                    if fut and not fut.done():
                        fut.set_result(data)
                    elif self._on_push is not None:
                        try:
                            self._on_push(data)
                        except Exception as exc:  # noqa: BLE001
                            self._logger(f"Push handler error: {exc}")
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                    break
        finally:
            # Fail any pending futures
            for fut in self._awaiting.values():
                if not fut.done():
                    fut.set_exception(SiegeniaError("Connection closed"))
            self._awaiting.clear()

    async def _send_request(self, command: str | Mapping[str, Any], params: Any | None = None) -> dict[str, Any]:
        if not self.connected:
            raise SiegeniaError("Not connected")

        self._req_id += 1
        req_id = self._req_id

        if isinstance(command, str):
            payload: dict[str, Any] = {"command": command, "id": req_id}
        else:
            payload = dict(command)
            payload["id"] = req_id

        if params is not None:
            payload["params"] = params

        assert self._ws is not None
        self._logger(f"SEND: {json.dumps(payload, separators=(',', ':'))}")
        await self._ws.send_str(json.dumps(payload))

        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._awaiting[req_id] = fut
        try:
            resp = await asyncio.wait_for(fut, timeout=self._response_timeout)
        except asyncio.TimeoutError as exc:  # noqa: PERF203
            self._awaiting.pop(req_id, None)
            raise SiegeniaError("Timeout waiting for response") from exc

        if not isinstance(resp, dict):
            raise SiegeniaError("Malformed response")

        status = resp.get("status")
        if status in {"not_authenticated", "authentication_error"}:
            raise AuthenticationError(status or "authentication_error")

        return resp

    async def login(self, user: str, password: str) -> None:
        resp = await self._send_request(
            {
                "command": "login",
                "user": user,
                "password": password,
                "long_life": False,
            }
        )
        if resp.get("status") != "ok":
            raise AuthenticationError(str(resp))

    async def keep_alive(self) -> None:
        await self._send_request("keepAlive", {"extend_session": True})

    async def start_heartbeat(self, interval: float = 10.0) -> None:
        async def _loop() -> None:
            try:
                while True:
                    await asyncio.sleep(interval)
                    try:
                        await self.keep_alive()
                    except Exception as exc:  # noqa: BLE001
                        self._logger(f"Heartbeat error: {exc}")
            except asyncio.CancelledError:  # task cancelled on disconnect
                return

        if self._hb_task is None or self._hb_task.done():
            self._hb_task = asyncio.create_task(_loop())

    async def get_device(self) -> dict[str, Any]:
        return await self._send_request("getDevice")

    async def get_device_params(self) -> dict[str, Any]:
        return await self._send_request("getDeviceParams")

    async def get_device_details(self) -> dict[str, Any]:
        return await self._send_request("getDeviceDetails")

    async def set_device_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return await self._send_request("setDeviceParams", params)

    async def open_close(self, sash: int, action: str) -> None:
        # Matches the Homebridge and .NET implementations
        await self.set_device_params({"openclose": {str(sash): action}})

    async def stop(self, sash: int) -> None:
        await self.set_device_params({"stop": {str(sash): True}})

    async def reset_device(self) -> None:
        await self._send_request("resetDevice")

    async def reboot_device(self) -> None:
        await self._send_request("rebootDevice")

    async def renew_cert(self) -> None:
        await self._send_request("renewCert")

    def set_push_callback(self, cb: Callable[[dict[str, Any]], None] | None) -> None:
        """Register a callback for unsolicited device messages.

        Called with the raw message dictionary from the device.
        """
        self._on_push = cb
