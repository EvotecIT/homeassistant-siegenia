from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_PREVENT_OPENING, DEFAULT_PREVENT_OPENING


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = coordinator.device_serial()
    async_add_entities([SiegeniaOpeningLockSwitch(coordinator, entry, serial)])


class SiegeniaOpeningLockSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "opening_lock"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, entry: ConfigEntry, serial: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._serial = serial
        self._attr_unique_id = f"{serial}-opening-lock"

    @property
    def is_on(self) -> bool:
        return bool(getattr(self.coordinator, "prevent_opening", DEFAULT_PREVENT_OPENING))

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self._set_lock(True)

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self._set_lock(False)

    def _set_lock(self, enabled: bool) -> None:
        options = dict(self._entry.options)
        options[CONF_PREVENT_OPENING] = enabled
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        self.coordinator.prevent_opening = enabled
        self.async_write_ha_state()
