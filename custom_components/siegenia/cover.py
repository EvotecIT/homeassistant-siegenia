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
    state_to_position,
    position_to_command,
    resolve_model,
    CONF_SLIDER_GAP_MAX,
    CONF_SLIDER_CWOL_MAX,
    CONF_SLIDER_STOP_OVER_DISPLAY,
    DEFAULT_GAP_MAX,
    DEFAULT_CWOL_MAX,
    DEFAULT_STOP_OVER_DISPLAY,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    states = (data.get("data") or {}).get("states") or {"0": None}
    entities = [SiegeniaWindowCover(coordinator, entry, int(sash)) for sash in sorted(map(int, states.keys()))]
    async_add_entities(entities)


class SiegeniaWindowCover(CoordinatorEntity, CoverEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "window"
    _attr_device_class = "window"
    _base_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    _with_slider = _base_features | CoverEntityFeature.SET_POSITION

    def __init__(self, coordinator, entry: SiegeniaConfigEntry, sash: int = 0) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sash = sash
        self._last_cmd: str | None = None
        # Use serial number if available
        serial = getattr(coordinator, "serial", None) or (coordinator.device_info or {}).get("data", {}).get("serialnr") if coordinator.device_info else None
        self._attr_unique_id = f"{serial or entry.unique_id or entry.data.get('host')}-sash-{self._sash}"
        # Options: enable/disable slider
        enable_slider = entry.options.get("enable_position_slider", True)
        self._attr_supported_features = self._with_slider if enable_slider else self._base_features

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        model = resolve_model(info)
        suggested = info.get("devicelocation") or info.get("devicefloor")
        ident = self._entry.unique_id or getattr(self.coordinator, "serial", None) or self._entry.data.get("host")
        return DeviceInfo(
            identifiers={(DOMAIN, ident)},
            manufacturer="Siegenia",
            model=str(model),
            name=info.get("devicename") or "Siegenia Device",
            sw_version=info.get("softwareversion"),
            hw_version=info.get("hardwareversion"),
            configuration_url=f"https://{self._entry.data.get('host')}:{self.coordinator.port}" if hasattr(self.coordinator, 'port') else None,
            suggested_area=suggested,
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
        return state_to_position(state) == 0

    @property
    def current_cover_position(self) -> int | None:
        state = self._current_state()
        if state is None:
            return None
        display = self._entry.options.get(CONF_SLIDER_STOP_OVER_DISPLAY, DEFAULT_STOP_OVER_DISPLAY)
        return state_to_position(state, stop_over_display=display)

    @property
    def is_opening(self) -> bool | None:
        state = self._current_state()
        if state != STATE_MOVING:
            return None
        last = self._last_cmd or getattr(self.coordinator, "get_last_cmd", lambda _s: None)(self._sash)
        # Treat manual movement as unknown direction
        try:
            if not self.coordinator.is_recent_cmd(self._sash, within=5.0):
                return None
        except Exception:
            pass
        return True if last in {"OPEN", "STOP_OVER", "GAP_VENT"} else None

    @property
    def is_closing(self) -> bool | None:
        state = self._current_state()
        if state != STATE_MOVING:
            return None
        last = self._last_cmd or getattr(self.coordinator, "get_last_cmd", lambda _s: None)(self._sash)
        try:
            if not self.coordinator.is_recent_cmd(self._sash, within=5.0):
                return None
        except Exception:
            pass
        return True if last in {"CLOSE", "CLOSE_WO_LOCK"} else None

    @property
    def extra_state_attributes(self) -> dict | None:
        try:
            state = self._current_state()
            moving = state == STATE_MOVING
            recent = self.coordinator.is_recent_cmd(self._sash, within=5.0)
            return {
                "manual_operation": bool(moving and not recent),
                "last_command": self.coordinator.get_last_cmd(self._sash),
            }
        except Exception:
            return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        self._last_cmd = "OPEN"
        try:
            self.coordinator.set_last_cmd(self._sash, self._last_cmd)
        except Exception:
            pass
        await self.coordinator.client.open_close(self._sash, "OPEN")
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        self._last_cmd = "CLOSE"
        try:
            self.coordinator.set_last_cmd(self._sash, self._last_cmd)
        except Exception:
            pass
        await self.coordinator.client.open_close(self._sash, "CLOSE")
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        self._last_cmd = "STOP"
        try:
            self.coordinator.set_last_cmd(self._sash, self._last_cmd)
        except Exception:
            pass
        await self.coordinator.client.stop(self._sash)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = int(kwargs.get(ATTR_POSITION, 0))
        gap_max = self._entry.options.get(CONF_SLIDER_GAP_MAX, DEFAULT_GAP_MAX)
        cwol_max = self._entry.options.get(CONF_SLIDER_CWOL_MAX, DEFAULT_CWOL_MAX)
        # ensure sane ordering
        try:
            gap_max = int(gap_max)
            cwol_max = int(cwol_max)
        except Exception:
            gap_max, cwol_max = DEFAULT_GAP_MAX, DEFAULT_CWOL_MAX
        if not (0 < gap_max < cwol_max < 100):
            gap_max, cwol_max = DEFAULT_GAP_MAX, DEFAULT_CWOL_MAX

        cmd = position_to_command(position, gap_max=gap_max, cwol_max=cwol_max)
        if cmd is None:
            return
        self._last_cmd = cmd
        try:
            self.coordinator.set_last_cmd(self._sash, self._last_cmd)
        except Exception:
            pass
        await self.coordinator.client.open_close(self._sash, cmd)
        await self.coordinator.async_request_refresh()
