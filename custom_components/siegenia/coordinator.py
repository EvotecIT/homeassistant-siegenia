from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import AuthenticationError, SiegeniaClient
from .const import (
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_POLL_INTERVAL,
)


class SiegeniaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL,
        session: ClientSession | None = None,
    ) -> None:
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=f"Siegenia {host}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.heartbeat_interval = heartbeat_interval
        self.client = SiegeniaClient(host, port=port, session=session, logger=self.logger.debug)
        self.device_info: dict[str, Any] | None = None

    async def async_setup(self) -> None:
        await self.client.connect()
        await self.client.login(self.username, self.password)
        await self.client.start_heartbeat(self.heartbeat_interval)
        # Push updates from device (no id) – update coordinator data immediately
        def _on_push(msg: dict[str, Any]) -> None:
            cmd = msg.get("command")
            if cmd in {"getDeviceParams", "deviceParams"} and "data" in msg:
                # Update data in HA thread-safe context
                self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, msg)
        self.client.set_push_callback(_on_push)
        # Prime device info once
        try:
            self.device_info = await self.client.get_device()
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Failed to get device info during setup: %s", exc)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if not self.client.connected:
                await self.client.connect()
                await self.client.login(self.username, self.password)
                await self.client.start_heartbeat(self.heartbeat_interval)
            params = await self.client.get_device_params()
            return params
        except AuthenticationError as err:
            # Trigger reauth flow in HA
            raise ConfigEntryAuthFailed from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(err) from err
