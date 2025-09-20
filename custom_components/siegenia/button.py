from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_TYPE_MAP

_ACTIONS = [
    ("Open", "OPEN"),
    ("Close", "CLOSE"),
    ("Gap Vent", "GAP_VENT"),
    ("Close w/o Lock", "CLOSE_WO_LOCK"),
    ("Stop Over", "STOP_OVER"),
    ("Stop", "STOP"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    info = (coordinator.device_info or {}).get("data", {})
    serial = info.get("serialnr") or entry.data.get("host")
    entities: list[ButtonEntity] = []
    for label, mode in _ACTIONS:
        entities.append(SiegeniaModeButton(coordinator, entry, serial, label, mode))
    async_add_entities(entities)


class SiegeniaModeButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator, entry: ConfigEntry, serial: str, label: str, mode: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._serial = serial
        self._label = label
        self._mode = mode
        self._attr_name = f"Siegenia: {label}"
        self._attr_unique_id = f"{serial}-button-{mode.lower()}"

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        model = DEVICE_TYPE_MAP.get(info.get("type"), info.get("type"))
        return DeviceInfo(
            identifiers={(DOMAIN, info.get("serialnr") or self._entry.data.get("host"))},
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
        await self.coordinator.async_request_refresh()

