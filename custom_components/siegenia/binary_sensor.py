from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_MOVING


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = (coordinator.device_info or {}).get("data", {}).get("serialnr") or entry.data.get("host")
    entities = [
        SiegeniaOnlineBinary(coordinator, entry, serial),
        SiegeniaMovingBinary(coordinator, entry, serial),
        SiegeniaWarningBinary(coordinator, entry, serial),
    ]
    async_add_entities(entities)


class SiegeniaOnlineBinary(CoordinatorEntity, BinarySensorEntity):
    _attr_name = "Siegenia Online"
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator, entry: ConfigEntry, serial: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._serial = serial
        self._attr_unique_id = f"{serial}-online"

    @property
    def is_on(self) -> bool | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        devstate = data.get("devicestate") or {}
        active = devstate.get("deviceactive")
        if active is None:
            # Fallback to update success
            return True if self.coordinator.last_update_success else None
        return bool(active)

    @property
    def device_info(self):
        info = (self.coordinator.device_info or {}).get("data", {})
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "manufacturer": "Siegenia",
            "name": info.get("devicename") or "Siegenia Device",
            "configuration_url": f"https://{self._entry.data.get('host')}:{getattr(self.coordinator, 'port', 443)}",
        }


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
            "configuration_url": f"https://{self._entry.data.get('host')}:{getattr(self.coordinator, 'port', 443)}",
        }


class SiegeniaWarningBinary(CoordinatorEntity, BinarySensorEntity):
    _attr_name = "Siegenia Warning Active"
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator, entry: ConfigEntry, serial: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._serial = serial
        self._attr_unique_id = f"{serial}-warning"

    @property
    def is_on(self) -> bool | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        warnings = data.get("warnings") or []
        return len(warnings) > 0

    @property
    def device_info(self):
        info = (self.coordinator.device_info or {}).get("data", {})
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "manufacturer": "Siegenia",
            "name": info.get("devicename") or "Siegenia Device",
        }
