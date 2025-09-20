from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SiegeniaConfigEntry
from .const import (
    DOMAIN,
    STATE_MOVING,
    STATE_TO_POSITION,
    position_to_command,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SiegeniaWindowCover(coordinator, entry)])


class SiegeniaWindowCover(CoordinatorEntity, CoverEntity):
    _attr_name = "Siegenia Window"
    _attr_device_class = "window"
    _base_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    _with_slider = _base_features | CoverEntityFeature.SET_POSITION

    def __init__(self, coordinator, entry: SiegeniaConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sash = 0
        # Use serial number if available
        serial = (coordinator.device_info or {}).get("data", {}).get("serialnr") if coordinator.device_info else None
        self._attr_unique_id = f"{serial or entry.data.get('host')}-sash-{self._sash}"
        # Options: enable/disable slider
        enable_slider = entry.options.get("enable_position_slider", True)
        self._attr_supported_features = self._with_slider if enable_slider else self._base_features

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        return DeviceInfo(
            identifiers={(DOMAIN, info.get("serialnr") or self._entry.data.get("host"))},
            manufacturer="Siegenia",
            model=info.get("type", 6),
            name=info.get("devicename") or "Siegenia Device",
            sw_version=info.get("softwareversion"),
            hw_version=info.get("hardwareversion"),
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.last_update_success

    def _current_state(self) -> str | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        states = data.get("states") or {}
        return states.get(str(self._sash))

    @property
    def is_closed(self) -> bool | None:
        state = self._current_state()
        if state is None:
            return None
        return STATE_TO_POSITION.get(state, 0) == 0

    @property
    def current_cover_position(self) -> int | None:
        state = self._current_state()
        if state is None:
            return None
        return STATE_TO_POSITION.get(state, 0)

    @property
    def is_opening(self) -> bool | None:
        return self._current_state() == STATE_MOVING  # Best-effort; device doesn't expose direction

    @property
    def is_closing(self) -> bool | None:
        return False  # Not distinguishable with current API; HA will show opening/closing from commands

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self.coordinator.client.open_close(self._sash, "OPEN")
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self.coordinator.client.open_close(self._sash, "CLOSE")
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self.coordinator.client.stop(self._sash)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = int(kwargs.get(ATTR_POSITION, 0))
        cmd = position_to_command(position)
        if cmd is None:
            return
        await self.coordinator.client.open_close(self._sash, cmd)
        await self.coordinator.async_request_refresh()
