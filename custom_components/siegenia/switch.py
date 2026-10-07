from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PREVENT_OPENING,
    DEFAULT_PREVENT_OPENING,
    DOMAIN,
    device_configuration_url,
    resolve_model,
)
from .coordinator import SiegeniaDataUpdateCoordinator
from .models import SiegeniaConfigEntry


# The WebSocket client correlates concurrent requests by ID; do not delay actions.
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: SiegeniaConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    serial = coordinator.device_serial()
    async_add_entities([SiegeniaOpeningLockSwitch(coordinator, entry, serial)])


class SiegeniaOpeningLockSwitch(CoordinatorEntity[SiegeniaDataUpdateCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "opening_lock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SiegeniaDataUpdateCoordinator, entry: SiegeniaConfigEntry, serial: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._serial = serial
        self._attr_unique_id = f"{serial}-opening-lock"

    @property
    def is_on(self) -> bool:
        return bool(getattr(self.coordinator, "prevent_opening", DEFAULT_PREVENT_OPENING))

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        ident = self.coordinator.device_identifier()
        return DeviceInfo(
            identifiers={(DOMAIN, ident)},
            manufacturer="Siegenia",
            model=resolve_model(info),
            name=info.get("devicename") or "Siegenia Device",
            sw_version=info.get("softwareversion"),
            hw_version=info.get("hardwareversion"),
            configuration_url=device_configuration_url(
                self._entry.data.get("host"),
                getattr(self.coordinator, "port", None),
                getattr(self.coordinator, "ws_protocol", None),
            ),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set_lock(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set_lock(False)

    def _set_lock(self, enabled: bool) -> None:
        options = dict(self._entry.options)
        options[CONF_PREVENT_OPENING] = enabled
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        # Mirror the option immediately so commands honor the new lock state
        # before Home Assistant finishes propagating the entry update.
        self.coordinator.prevent_opening = enabled
        self.async_write_ha_state()
