from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SiegeniaStopoverNumber(coordinator, entry)])


class SiegeniaStopoverNumber(CoordinatorEntity, NumberEntity):
    _attr_name = "Siegenia Stopover Distance"
    _attr_mode = "slider"
    _attr_native_unit_of_measurement = "dm"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        serial = (coordinator.device_info or {}).get("data", {}).get("serialnr") or entry.data.get("host")
        self._attr_unique_id = f"{serial}-stopover"

    @property
    def native_min_value(self) -> float:
        data = (self.coordinator.data or {}).get("data", {})
        return 0.0

    @property
    def native_max_value(self) -> float:
        data = (self.coordinator.data or {}).get("data", {})
        max_so = data.get("max_stopover")
        return float(max_so) if max_so is not None else 20.0

    @property
    def native_step(self) -> float:
        return 1.0

    @property
    def native_value(self) -> float | None:
        data = (self.coordinator.data or {}).get("data", {})
        val = data.get("stopover")
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        # Device expects integer decimeters
        await self.coordinator.client.set_device_params({"stopover": int(value)})
        await self.coordinator.async_request_refresh()

