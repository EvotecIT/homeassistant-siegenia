from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_MOVING


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = (coordinator.device_info or {}).get("data", {}).get("serialnr") or entry.data.get("host")
    async_add_entities([SiegeniaMovingBinary(coordinator, entry, serial)])


class SiegeniaMovingBinary(CoordinatorEntity, BinarySensorEntity):
    _attr_name = "Siegenia Window Moving"
    _attr_icon = "mdi:motion"

    def __init__(self, coordinator, entry: ConfigEntry, serial: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._serial = serial
        self._attr_unique_id = f"{serial}-moving"

    @property
    def is_on(self) -> bool | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        state = (data.get("states") or {}).get("0")
        return state == STATE_MOVING

    @property
    def device_info(self):
        info = (self.coordinator.device_info or {}).get("data", {})
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "manufacturer": "Siegenia",
            "name": info.get("devicename") or "Siegenia Device",
        }

