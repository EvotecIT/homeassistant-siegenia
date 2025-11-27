from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_TYPE_MAP, CONF_ENABLE_BUTTONS

_ACTIONS = [
    ("open", "OPEN"),
    ("close", "CLOSE"),
    ("gap_vent", "GAP_VENT"),
    ("close_wo_lock", "CLOSE_WO_LOCK"),
    ("stop_over", "STOP_OVER"),
    ("stop", "STOP"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    # Respect option: buttons disabled by default
    if not entry.options.get(CONF_ENABLE_BUTTONS, False):
        return
    coordinator = hass.data[DOMAIN][entry.entry_id]
    info = (coordinator.device_info or {}).get("data", {})
    serial = getattr(coordinator, "serial", None) or info.get("serialnr") or entry.unique_id or entry.data.get("host")
    entities: list[ButtonEntity] = []
    for key, mode in _ACTIONS:
        entities.append(SiegeniaModeButton(coordinator, entry, serial, key, mode))
    async_add_entities(entities)


class SiegeniaModeButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator, entry: ConfigEntry, serial: str, key: str, mode: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._serial = serial
        self._label = key
        self._mode = mode
        self._attr_has_entity_name = True
        self._attr_translation_key = key
        self._attr_unique_id = f"{serial}-button-{key}"

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        model = DEVICE_TYPE_MAP.get(info.get("type"), info.get("type"))
        ident = getattr(self.coordinator, "device_identifier", lambda: None)() or info.get("serialnr") or self._entry.data.get("host")
        return DeviceInfo(
            identifiers={(DOMAIN, ident)},
            manufacturer="Siegenia",
            model=str(model),
            name=info.get("devicename") or "Siegenia Device",
        )

    async def async_press(self) -> None:
        sash = 0
        if self._mode == "STOP":
            await self.coordinator.client.stop(sash)
        else:
            await self.coordinator.client.open_close(sash, self._mode)
        try:
            self.coordinator.set_last_cmd(sash, self._mode)
        except Exception:
            pass
        await self.coordinator.async_request_refresh()
