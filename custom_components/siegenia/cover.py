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
    CMD_CLOSE_WO_LOCK,
    CONF_SLIDER_GAP_MAX,
    CONF_SLIDER_CWOL_MAX,
    CONF_SLIDER_STOP_OVER_DISPLAY,
    DEFAULT_GAP_MAX,
    DEFAULT_CWOL_MAX,
    DEFAULT_STOP_OVER_DISPLAY,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    known_sashes: set[int] = set()

    def _current_sashes() -> list[int]:
        data = coordinator.data or {}
        states = (data.get("data") or {}).get("states") or {}
        if not states:
            return [0]
        return sorted(map(int, states.keys()))

    def _add_missing() -> None:
        new_entities = []
        for sash in _current_sashes():
            if sash in known_sashes:
                continue
            known_sashes.add(sash)
            new_entities.append(SiegeniaWindowCover(coordinator, entry, int(sash)))
        if new_entities:
            async_add_entities(new_entities)

    _add_missing()
    entry.async_on_unload(coordinator.async_add_listener(_add_missing))


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
        serial = coordinator.device_serial()
        self._attr_unique_id = f"{serial}-sash-{self._sash}"
        # Options: enable/disable slider
        enable_slider = entry.options.get("enable_position_slider", True)
        self._attr_supported_features = self._with_slider if enable_slider else self._base_features

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        model = resolve_model(info)
        suggested = info.get("devicelocation") or info.get("devicefloor")
        ident = self.coordinator.device_identifier()
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
        pos = state_to_position(state)
        if pos is None:
            return None
        return pos == 0

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
        return True if last in {"CLOSE", CMD_CLOSE_WO_LOCK} else None

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
        await self.coordinator.async_send_command(
            self._sash,
            "OPEN",
            source="cover",
            entity_id=getattr(self, "entity_id", None),
            context=getattr(self, "_context", None),
        )
        self._last_cmd = "OPEN"
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(
            self._sash,
            "CLOSE",
            source="cover",
            entity_id=getattr(self, "entity_id", None),
            context=getattr(self, "_context", None),
        )
        self._last_cmd = "CLOSE"
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(
            self._sash,
            "STOP",
            source="cover",
            entity_id=getattr(self, "entity_id", None),
            context=getattr(self, "_context", None),
        )
        self._last_cmd = "STOP"
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
        await self.coordinator.async_send_command(
            self._sash,
            cmd,
            source="cover_position",
            entity_id=getattr(self, "entity_id", None),
            context=getattr(self, "_context", None),
        )
        self._last_cmd = cmd
        await self.coordinator.async_request_refresh()
