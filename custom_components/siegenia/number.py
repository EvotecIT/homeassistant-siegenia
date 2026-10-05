from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, resolve_model
from .coordinator import SiegeniaDataUpdateCoordinator
from .models import SiegeniaConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: SiegeniaConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([SiegeniaStopoverNumber(coordinator, entry)])


class SiegeniaStopoverNumber(CoordinatorEntity[SiegeniaDataUpdateCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "stopover_distance"
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "dm"

    def __init__(self, coordinator: SiegeniaDataUpdateCoordinator, entry: SiegeniaConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        serial = coordinator.device_serial()
        self._attr_unique_id = f"{serial}-stopover"
        self._serial = serial

    @property
    def native_min_value(self) -> float:
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
        await self.coordinator.async_set_device_params(
            {"stopover": int(value)},
            action_name="set the stopover distance",
        )
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        ident = self.coordinator.device_identifier()
        return {
            "identifiers": {(DOMAIN, ident)},
            "manufacturer": "Siegenia",
            "name": info.get("devicename") or "Siegenia Device",
            "model": resolve_model(info),
        }
