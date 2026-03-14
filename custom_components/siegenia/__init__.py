from __future__ import annotations

from pathlib import Path
from datetime import timedelta

from typing import TYPE_CHECKING
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import asyncio
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN,
    CONF_HEARTBEAT_INTERVAL,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_USERNAME,
    CONF_HOST,
    CONF_AUTO_DISCOVER,
    CONF_EXTENDED_DISCOVERY,
    CONF_WS_PROTOCOL,
    DEFAULT_WS_PROTOCOL,
    DEFAULT_AUTO_DISCOVER,
    DEFAULT_EXTENDED_DISCOVERY,
    CONF_SERIAL,
    MIGRATION_DEVICES_V2,
    PLATFORMS,
    CONF_WARNING_NOTIFICATIONS,
    CONF_WARNING_EVENTS,
    CONF_DEBUG,
    CONF_INFORMATIONAL,
    CONF_MOTION_INTERVAL,
    CONF_IDLE_INTERVAL,
    DEFAULT_MOTION_INTERVAL,
    DEFAULT_IDLE_INTERVAL,
    CONF_PREVENT_OPENING,
    DEFAULT_PREVENT_OPENING,
)
from .coordinator import SiegeniaDataUpdateCoordinator
from .device_registry import async_merge_devices
from .__init_services__ import async_setup_services


# Compatible type alias across HA versions (ConfigEntry may be non-generic)
if TYPE_CHECKING:
    # During type checking use the generic form
    from homeassistant.config_entries import ConfigEntry as _Cfg
    SiegeniaConfigEntry = _Cfg[SiegeniaDataUpdateCoordinator]  # type: ignore[misc]
else:  # runtime: fall back to non-parameterized
    SiegeniaConfigEntry = ConfigEntry  # type: ignore[assignment]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    from .const import DEFAULT_POLL_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL

    poll_interval = entry.options.get(CONF_POLL_INTERVAL, data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
    heartbeat_interval = entry.options.get(CONF_HEARTBEAT_INTERVAL, data.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL))

    coordinator = SiegeniaDataUpdateCoordinator(
        hass,
        entry=entry,
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        ws_protocol=data.get(CONF_WS_PROTOCOL, DEFAULT_WS_PROTOCOL),
        auto_discover=data.get(CONF_AUTO_DISCOVER, DEFAULT_AUTO_DISCOVER),
        extended_discovery=data.get(CONF_EXTENDED_DISCOVERY, DEFAULT_EXTENDED_DISCOVERY),
        poll_interval=poll_interval,
        heartbeat_interval=heartbeat_interval,
    )
    # Pass options for warnings routing
    coordinator.warning_notifications = entry.options.get(CONF_WARNING_NOTIFICATIONS, True)
    coordinator.warning_events = entry.options.get(CONF_WARNING_EVENTS, True)
    coordinator.debug_logging = entry.options.get(CONF_DEBUG, False)
    coordinator.informational_logging = entry.options.get(CONF_INFORMATIONAL, False)
    coordinator.prevent_opening = entry.options.get(CONF_PREVENT_OPENING, DEFAULT_PREVENT_OPENING)
    # Advanced intervals
    motion_s = entry.options.get(CONF_MOTION_INTERVAL, DEFAULT_MOTION_INTERVAL)
    idle_s = entry.options.get(CONF_IDLE_INTERVAL, DEFAULT_IDLE_INTERVAL)
    coordinator._motion_interval = timedelta(seconds=motion_s)  # type: ignore[attr-defined]
    coordinator._idle_interval = timedelta(seconds=idle_s)      # type: ignore[attr-defined]

    try:
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        # Wrong credentials should still trigger HA's reauth flow
        raise
    except Exception as exc:  # noqa: BLE001
        # Allow setup to continue so options/services stay available; coordinator will retry in background
        coordinator.logger.warning("Initial connection failed; will retry in background: %s", exc)

    # Merge duplicate devices once per entry
    _lock_key = f"{DOMAIN}_migration_lock_{entry.entry_id}"
    if _lock_key not in hass.data:
        hass.data[_lock_key] = asyncio.Lock()
    async with hass.data[_lock_key]:
        if not entry.data.get(MIGRATION_DEVICES_V2):
            try:
                await _async_migrate_devices(hass, entry)
                hass.config_entries.async_update_entry(entry, data={**entry.data, MIGRATION_DEVICES_V2: True})
            except Exception as exc:  # noqa: BLE001
                coordinator.logger.debug("Device migration skipped: %s", exc)

    hass.data.setdefault(entry.domain, {})[entry.entry_id] = coordinator

    # Register services once per HA instance using a marker
    marker = f"{DOMAIN}_services_registered"
    if not hass.data.get(marker):
        await async_setup_services(hass)
        hass.data[marker] = True

    # Serve bundled dashboard icons so users can reference them without copying to /local.
    # Integration branding is provided natively via custom_components/siegenia/brand/.
    static_marker = f"{DOMAIN}_static_paths"
    if not hass.data.get(static_marker):
        try:
            import os
            testing = os.environ.get("PYTEST_CURRENT_TEST") is not None
            icons_path = Path(__file__).resolve().parents[2] / "assets" / "icons"
            if icons_path.exists() and not testing:
                hass.http.register_static_path("/siegenia-static/icons", str(icons_path), cache_headers=True)  # type: ignore[attr-defined]
                hass.data[static_marker] = True
        except Exception:  # noqa: BLE001
            # If HTTP component is not ready or API changed, skip silently; HA branding still works natively.
            pass

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: SiegeniaDataUpdateCoordinator = hass.data[entry.domain].pop(entry.entry_id)
    await coordinator.client.disconnect()
    return unload_ok


async def _async_migrate_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    serial = entry.data.get(CONF_SERIAL) or entry.unique_id
    host = entry.data.get(CONF_HOST)
    await async_merge_devices(hass, entry.entry_id, serial=serial, host=host)
