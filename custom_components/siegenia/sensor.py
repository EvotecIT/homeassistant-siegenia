from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, resolve_model


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = (coordinator.device_info or {}).get("data", {}).get("serialnr") or entry.data.get("host")
    entities = []
    if entry.options.get("enable_state_sensor", True):
        entities.append(SiegeniaStateSensor(coordinator, entry, serial))
    if entry.options.get("enable_open_count", True):
        entities.append(SiegeniaOpenCountSensor(coordinator, entry, serial))
    # Always expose warnings count/text and firmware update if present
    entities.append(SiegeniaWarningsCountSensor(coordinator, entry, serial))
    entities.append(SiegeniaWarningsTextSensor(coordinator, entry, serial))
    entities.append(SiegeniaFirmwareUpdateSensor(coordinator, entry, serial))
    # Timer-related sensors
    entities.append(SiegeniaTimerEnabledSensor(coordinator, entry, serial))
    entities.append(SiegeniaTimerRemainingSensor(coordinator, entry, serial))
    # Operation source (command vs manual vs idle)
    entities.append(SiegeniaOperationSourceSensor(coordinator, entry, serial))
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
            "model": resolve_model(info),
            "sw_version": info.get("softwareversion"),
        }


class SiegeniaStateSensor(_BaseSiegeniaEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:window-closed-variant"
    _attr_translation_key = "window_state"

    @property
    def unique_id(self) -> str:  # noqa: D401
        return f"{self._serial}-state"

    @property
    def native_value(self) -> str | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        states = data.get("states") or {}
        return states.get("0")


class SiegeniaWarningsCountSensor(_BaseSiegeniaEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "warnings_count"
    _attr_icon = "mdi:alert"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:  # noqa: D401
        return f"{self._serial}-warnings-count"

    @property
    def native_value(self) -> int:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        warnings = data.get("warnings") or []
        return len(warnings)


class SiegeniaWarningsTextSensor(_BaseSiegeniaEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "warnings"
    _attr_icon = "mdi:alert-octagon"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:  # noqa: D401
        return f"{self._serial}-warnings-text"

    @property
    def native_value(self) -> str | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        warnings = data.get("warnings") or []
        if not warnings:
            return "None"
        # warnings entries may be strings or dicts; stringify safely
        return "; ".join(map(lambda w: w if isinstance(w, str) else str(w), warnings))


class SiegeniaFirmwareUpdateSensor(_BaseSiegeniaEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "firmware_update"
    _attr_icon = "mdi:update"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:  # noqa: D401
        return f"{self._serial}-firmware-update"

    @property
    def native_value(self) -> str | None:
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        val = data.get("firmware_update")
        if val is None:
            # try getDevice payload
            info = (self.coordinator.device_info or {}).get("data", {})
            val = info.get("firmware_update")
        if not val:
            return "None"
        return "Available"


class SiegeniaTimerEnabledSensor(_BaseSiegeniaEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "timer_enabled"
    _attr_icon = "mdi:timer"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self._serial}-timer-enabled"

    @property
    def native_value(self) -> str | None:
        data = (self.coordinator.data or {}).get("data", {})
        timer = data.get("timer") or {}
        enabled = timer.get("enabled")
        if enabled is None:
            return None
        return "on" if enabled else "off"


class SiegeniaTimerRemainingSensor(_BaseSiegeniaEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "timer_remaining"
    _attr_icon = "mdi:timer-sand"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self._serial}-timer-remaining"

    @property
    def native_value(self) -> str | None:
        data = (self.coordinator.data or {}).get("data", {})
        timer = data.get("timer") or {}
        remaining = timer.get("remainingtime") or {}
        h = remaining.get("hour")
        m = remaining.get("minute")
        if h is None or m is None:
            return None
        return f"{int(h):02d}:{int(m):02d}"


class SiegeniaOperationSourceSensor(_BaseSiegeniaEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "operation_source"
    _attr_icon = "mdi:account-arrow-right"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self._serial}-operation-source"

    @property
    def native_value(self) -> str | None:
        data = (self.coordinator.data or {}).get("data", {})
        states = data.get("states") or {}
        state = states.get("0")
        if state == "MOVING":
            try:
                return "COMMAND" if self.coordinator.is_recent_cmd(0, within=5.0) else "MANUAL"
            except Exception:
                return "MANUAL"
        return "IDLE"

    @property
    def extra_state_attributes(self) -> dict | None:
        try:
            return {
                "last_command": self.coordinator.get_last_cmd(0),
                "last_stable_state": self.coordinator.get_last_stable_state(0),
            }
        except Exception:
            return None


class SiegeniaOpenCountSensor(_BaseSiegeniaEntity, RestoreEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "open_count"
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    # Keep unit None for LTS compatibility

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
