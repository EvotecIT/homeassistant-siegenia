from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_TO_POSITION


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = (coordinator.device_info or {}).get("data", {}).get("serialnr") or entry.data.get("host")
    entities = []
    if entry.options.get("enable_state_sensor", True):
        entities.append(SiegeniaStateSensor(coordinator, entry, serial))
    if entry.options.get("enable_open_count", True):
        entities.append(SiegeniaOpenCountSensor(coordinator, entry, serial))
    if entities:
        async_add_entities(entities)


class _BaseSiegeniaEntity(CoordinatorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, serial: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._serial = serial

    @property
    def device_info(self):  # noqa: D401 - Home Assistant style
        info = (self.coordinator.device_info or {}).get("data", {})
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "manufacturer": "Siegenia",
            "name": info.get("devicename") or "Siegenia Device",
            "model": info.get("type", 6),
            "sw_version": info.get("softwareversion"),
        }


class SiegeniaStateSensor(_BaseSiegeniaEntity, SensorEntity):
    _attr_name = "Siegenia Window State"
    _attr_icon = "mdi:window-closed-variant"

    @property
    def unique_id(self) -> str:  # noqa: D401
        return f"{self._serial}-state"

    @property
    def native_value(self) -> str | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        states = data.get("states") or {}
        return states.get("0")


class SiegeniaOpenCountSensor(_BaseSiegeniaEntity, RestoreEntity, SensorEntity):
    _attr_name = "Siegenia Window Open Count"
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    # Use a plain numeric counter: no device_class; provide a unit for statistics
    _attr_native_unit_of_measurement = "count"

    def __init__(self, coordinator, entry: ConfigEntry, serial: str) -> None:
        super().__init__(coordinator, entry, serial)
        self._count: int = 0
        self._last_was_open = False

    @property
    def unique_id(self) -> str:  # noqa: D401
        return f"{self._serial}-open-count"

    @property
    def native_value(self) -> int | None:
        return self._count

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state and state.state.isdigit():
            self._count = int(state.state)
        # Initialize last state
        self._last_was_open = self._is_open()

        # Subscribe to coordinator updates
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

    def _is_open(self) -> bool:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        state = (data.get("states") or {}).get("0")
        return state == "OPEN"

    def _handle_coordinator_update(self) -> None:
        is_open = self._is_open()
        if is_open and not self._last_was_open:
            self._count += 1
            self.async_write_ha_state()
        self._last_was_open = is_open
