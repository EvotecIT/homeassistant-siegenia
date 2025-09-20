from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    SELECT_OPTIONS,
    STATE_TO_SELECT,
    STATE_MOVING,
    OPTION_TO_CMD,
    CMD_TO_OPTION,
)

# Friendly labels for options (fallback English)
# We expose raw options (OPEN/CLOSE/…) and let HA translate via
# translations: entity.select.mode.state.*


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    states = (data.get("data") or {}).get("states") or {"0": None}
    entities = [SiegeniaModeSelect(coordinator, entry, int(sash)) for sash in sorted(map(int, states.keys()))]
    async_add_entities(entities)


class SiegeniaModeSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    # Raw options; frontend shows translated labels
    _attr_options = SELECT_OPTIONS
    _attr_translation_key = "mode"

    def __init__(self, coordinator, entry: ConfigEntry, sash: int) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sash = sash
        serial = (coordinator.device_info or {}).get("data", {}).get("serialnr") or entry.data.get("host")
        self._attr_unique_id = f"{serial}-mode-sash-{sash}"
        self._serial = serial

    @property
    def current_option(self) -> str | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        state = (data.get("states") or {}).get(str(self._sash))
        raw = STATE_TO_SELECT.get(state)
        # If device reports MOVING or an unmapped state, keep last commanded option
        if raw is None or state == STATE_MOVING:
            try:
                # Prefer a recent command; otherwise fallback to last stable state mapping
                if self.coordinator.is_recent_cmd(self._sash, within=5.0):
                    last_cmd = self.coordinator.get_last_cmd(self._sash)
                    if last_cmd:
                        last_opt = CMD_TO_OPTION.get(last_cmd)
                        if last_opt in self._attr_options:
                            return last_opt
                stable = self.coordinator.get_last_stable_state(self._sash)
                fallback = STATE_TO_SELECT.get(stable)
                if fallback in self._attr_options:
                    return fallback
            except Exception:
                pass
        return raw

    async def async_select_option(self, option: str) -> None:
        # Option is lower-case; map to device command
        if option == "stop":
            await self.coordinator.client.stop(self._sash)
        else:
            await self.coordinator.client.open_close(self._sash, OPTION_TO_CMD.get(option, option.upper()))
        # Remember last command for motion inference across entities
        try:
            self.coordinator.set_last_cmd(self._sash, OPTION_TO_CMD.get(option, option.upper()))
        except Exception:
            pass
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict | None:
        try:
            params = self.coordinator.data or {}
            data = params.get("data") or {}
            state = (data.get("states") or {}).get(str(self._sash))
            moving = state == STATE_MOVING
            recent = self.coordinator.is_recent_cmd(self._sash, within=5.0)
            manual = bool(moving and not recent)
            stable = self.coordinator.get_last_stable_state(self._sash)
            return {
                "moving": moving,
                "manual_operation": manual,
                "last_command": self.coordinator.get_last_cmd(self._sash),
                "last_stable_state": stable,
            }
        except Exception:
            return None

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            manufacturer="Siegenia",
            name=info.get("devicename") or "Siegenia Device",
        )
