from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, resolve_model


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:  # type: ignore[no-untyped-def]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SiegeniaFirmwareUpdate(coordinator, entry)])


class SiegeniaFirmwareUpdate(CoordinatorEntity, UpdateEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        serial = getattr(coordinator, "serial", None) or (coordinator.device_info or {}).get("data", {}).get("serialnr") or entry.unique_id or entry.data.get("host")
        self._attr_unique_id = f"{serial}-firmware-update"
        self._serial = serial

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.last_update_success

    @property
    def installed_version(self) -> str | None:
        info = (self.coordinator.device_info or {}).get("data", {})
        return info.get("softwareversion") or "unknown"

    @property
    def latest_version(self) -> str | None:
        # The device does not report the target firmware version via local API.
        # Return installed version to avoid an "unknown" UI state when up-to-date.
        return self.installed_version

    @property
    def release_url(self) -> str | None:  # noqa: D401
        return None

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.device_info or {}).get("data", {})
        model = resolve_model(info)
        suggested = info.get("devicelocation") or info.get("devicefloor")
        ident = getattr(self.coordinator, "device_identifier", lambda: None)() or info.get("serialnr") or self._serial
        return DeviceInfo(
            identifiers={(DOMAIN, ident)},
            manufacturer="Siegenia",
            model=str(model),
            name=info.get("devicename") or "Siegenia Device",
            sw_version=info.get("softwareversion"),
            configuration_url=f"https://{self._entry.data.get('host')}:{self.coordinator.port}" if hasattr(self.coordinator, 'port') else None,
            suggested_area=suggested,
        )

    @property
    def in_progress(self) -> bool | None:  # noqa: D401
        return None

    @property
    def available_updates(self) -> int | None:  # noqa: D401
        # Map firmware_update flag: non-zero means available
        params = self.coordinator.data or {}
        data = params.get("data") or {}
        flag = data.get("firmware_update")
        if flag is None:
            info = (self.coordinator.device_info or {}).get("data", {})
            flag = info.get("firmware_update")
        return 1 if flag not in (None, 0, "0") else 0

    @property
    def is_on(self) -> bool:
        # UpdateEntity uses state "on" when an update is available
        return bool(self.available_updates)
