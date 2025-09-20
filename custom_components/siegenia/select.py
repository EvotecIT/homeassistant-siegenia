from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, SELECT_OPTIONS, STATE_TO_SELECT

# Friendly labels for options (fallback English)
LABEL_BY_VALUE = {
    "OPEN": "Open",
    "CLOSE": "Close",
    "GAP_VENT": "Gap Vent",
    "CLOSE_WO_LOCK": "Close (no lock)",
    "STOP_OVER": "Stop Over",
    "STOP": "Stop",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    states = (data.get("data") or {}).get("states") or {"0": None}
    entities = [SiegeniaModeSelect(coordinator, entry, int(sash)) for sash in sorted(map(int, states.keys()))]
    async_add_entities(entities)


class SiegeniaModeSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_options = list(LABEL_BY_VALUE.values())
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
        return LABEL_BY_VALUE.get(raw)

    async def async_select_option(self, option: str) -> None:
        # Dispatch to device (map label back to raw)
        value_by_label = {v: k for k, v in LABEL_BY_VALUE.items()}
        raw = value_by_label.get(option, option)
        if raw == "STOP":
            await self.coordinator.client.stop(self._sash)
        else:
            await self.coordinator.client.open_close(self._sash, raw)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            manufacturer="Siegenia",
            name=info.get("devicename") or "Siegenia Device",
        )
