from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_call_later
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
        # Push/poll strategy
        self._default_interval = timedelta(seconds=poll_interval)
        self._push_interval = timedelta(seconds=max(poll_interval * 6, 30))
        self._idle_interval = timedelta(seconds=max(poll_interval * 10, 60))
        self._motion_interval = timedelta(seconds=max(1, min(2, poll_interval)))
        self._push_idle_timeout = 60
        self._last_push_monotonic: float | None = None
        self._revert_handle = None
        # Warnings tracking
        self._last_warnings: str | None = None
        # Options toggles (set from setup_entry)
        self.warning_notifications: bool = True
        self.warning_events: bool = True
        self._motion_revert_handle = None

    async def async_setup(self) -> None:
        await self.client.connect()
        await self.client.login(self.username, self.password)
        await self.client.start_heartbeat(self.heartbeat_interval)
        # Push updates from device (no id) – update coordinator data immediately
        def _on_push(msg: dict[str, Any]) -> None:
            cmd = msg.get("command")
            if cmd in {"getDeviceParams", "deviceParams"} and "data" in msg:
                # Update data and switch to push-optimized interval
                self.hass.loop.call_soon_threadsafe(self._handle_push_update, msg)
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
            self._adjust_interval(params)
            # Check warnings on polled data too
            self._handle_warnings(params)
            return params
        except AuthenticationError as err:
            # Trigger reauth flow in HA
            raise ConfigEntryAuthFailed from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(err) from err

    def _handle_push_update(self, msg: dict[str, Any]) -> None:
        # Mark push as active; slow down poller while push is flowing
        self._last_push_monotonic = time.monotonic()
        # Prefer motion interval if moving; else push interval
        moving = any(v == "MOVING" for v in (msg.get("data") or {}).get("states", {}).values())
        if moving:
            self.update_interval = self._motion_interval
        else:
            self.update_interval = self._push_interval

        # schedule revert after idle timeout
        if self._revert_handle is not None:
            self._revert_handle()  # cancel
            self._revert_handle = None

        def _revert(_now):  # noqa: ANN001
            if self._last_push_monotonic and (time.monotonic() - self._last_push_monotonic) >= self._push_idle_timeout:
                self.update_interval = self._default_interval
                self._revert_handle = None
            else:
                self._revert_handle = async_call_later(self.hass, self._push_idle_timeout, _revert)

        self._revert_handle = async_call_later(self.hass, self._push_idle_timeout, _revert)
        # Merge push payload into last known params to avoid losing keys (e.g., timer)
        merged = self.data or {}
        try:
            if not merged:
                merged = msg
            else:
                md = dict(merged)
                nd = dict(msg)
                mdata = dict(md.get("data") or {})
                ndata = dict(nd.get("data") or {})
                mdata.update(ndata)
                md["data"] = mdata
                merged = md
        except Exception:
            merged = msg
        self.async_set_updated_data(merged)
        self._handle_warnings(msg)

    def _adjust_interval(self, payload: dict[str, Any]) -> None:
        data = (payload or {}).get("data") or {}
        states = (data.get("states") or {}).values()
        if any(s == "MOVING" for s in states):
            # Speed up while moving
            self.update_interval = self._motion_interval
            # schedule a revert after short delay if motion stops
            if self._motion_revert_handle is not None:
                self._motion_revert_handle()
                self._motion_revert_handle = None

            def _revert(_now):  # noqa: ANN001
                # If not moving anymore, go to idle interval
                self.update_interval = self._idle_interval
                self._motion_revert_handle = None

            from homeassistant.helpers.event import async_call_later as _later

            self._motion_revert_handle = _later(self.hass, 10, _revert)
        else:
            # Idle: lengthen
            self.update_interval = self._idle_interval

    def _handle_warnings(self, payload: dict[str, Any]) -> None:
        data = (payload or {}).get("data") or {}
        warnings = data.get("warnings") or []
        key = ";".join(map(lambda w: w if isinstance(w, str) else str(w), warnings)) if warnings else ""
        if key == (self._last_warnings or ""):
            return
        serial = ((self.device_info or {}).get("data", {}) or {}).get("serialnr")
        notif_id = f"siegenia_warning_{serial or self.host}"
        if warnings:
            if self.warning_notifications:
                try:
                    self.hass.components.persistent_notification.async_create(
                        key or "Warning reported",
                        title="Siegenia Warning",
                        notification_id=notif_id,
                    )
                except Exception:
                    pass
            if self.warning_events:
                self.hass.bus.async_fire(
                    "siegenia_warning",
                    {"host": self.host, "serial": serial, "warnings": warnings, "cleared": False},
                )
        else:
            if self.warning_notifications:
                try:
                    self.hass.components.persistent_notification.async_dismiss(notif_id)
                except Exception:
                    pass
            if self.warning_events:
                self.hass.bus.async_fire(
                    "siegenia_warning",
                    {"host": self.host, "serial": serial, "warnings": [], "cleared": True},
                )
        self._last_warnings = key
