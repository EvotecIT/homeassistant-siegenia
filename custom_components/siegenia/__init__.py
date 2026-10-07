from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

# Public import works on minimum and current HA; current HA omits a typed re-export.
from homeassistant.components.http import StaticPathConfig  # type: ignore[attr-defined]
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .__init_services__ import async_setup_services
from .const import (
    CONF_AUTO_DISCOVER,
    CONF_DEBUG,
    CONF_EXTENDED_DISCOVERY,
    CONF_HEARTBEAT_INTERVAL,
    CONF_HOST,
    CONF_IDLE_INTERVAL,
    CONF_INFORMATIONAL,
    CONF_MOTION_INTERVAL,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_PREVENT_OPENING,
    CONF_SERIAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_WARNING_EVENTS,
    CONF_WARNING_NOTIFICATIONS,
    CONF_WS_PROTOCOL,
    DEFAULT_AUTO_DISCOVER,
    DEFAULT_EXTENDED_DISCOVERY,
    DEFAULT_IDLE_INTERVAL,
    DEFAULT_MOTION_INTERVAL,
    DEFAULT_PREVENT_OPENING,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WS_PROTOCOL,
    DOMAIN,
    MIGRATION_DEVICES_V2,
    PLATFORMS,
)
from .coordinator import SiegeniaDataUpdateCoordinator, async_clear_connection_issue
from .device_registry import async_merge_devices
from .models import SiegeniaConfigEntry

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration actions and installed dashboard icons once."""
    await async_setup_services(hass)
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            "/siegenia-static/icons", str(Path(__file__).parent / "icons"), True,
        ),
    ])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SiegeniaConfigEntry) -> bool:
    data = entry.data
    from .const import DEFAULT_HEARTBEAT_INTERVAL, DEFAULT_POLL_INTERVAL

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
        verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        auto_discover=data.get(CONF_AUTO_DISCOVER, DEFAULT_AUTO_DISCOVER),
        extended_discovery=data.get(CONF_EXTENDED_DISCOVERY, DEFAULT_EXTENDED_DISCOVERY),
        poll_interval=poll_interval,
        heartbeat_interval=heartbeat_interval,
        session=async_get_clientsession(hass),
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
    coordinator._motion_interval = timedelta(seconds=motion_s)
    coordinator._idle_interval = timedelta(seconds=idle_s)

    async def _async_shutdown_coordinator() -> None:
        """Stop connections and background tasks owned by the coordinator."""
        await coordinator.async_shutdown()

    async def _async_shutdown_on_stop(_: Event) -> None:
        """Disconnect background client tasks before Home Assistant stops."""
        await _async_shutdown_coordinator()

    remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        _async_shutdown_on_stop,
    )

    try:
        await _async_finish_setup(hass, entry, coordinator)
    except (asyncio.CancelledError, Exception):
        remove_stop_listener()
        try:
            await _async_shutdown_coordinator()
        except Exception as err:  # noqa: BLE001 - preserve the setup failure
            coordinator.logger.warning(
                "Failed to disconnect Siegenia client after setup error: %s",
                err,
            )
        raise

    entry.async_on_unload(remove_stop_listener)
    configured_options = dict(entry.options)

    async def _async_options_updated(
        hass: HomeAssistant, updated_entry: SiegeniaConfigEntry
    ) -> None:
        """Apply changed options without reloading on discovery data updates."""
        nonlocal configured_options
        new_options = dict(updated_entry.options)
        if new_options == configured_options:
            return
        # The opening-lock switch applies immediately without interrupting devices.
        coordinator.prevent_opening = new_options.get(
            CONF_PREVENT_OPENING, DEFAULT_PREVENT_OPENING
        )
        requires_reload = (
            {key: value for key, value in new_options.items() if key != CONF_PREVENT_OPENING}
            != {key: value for key, value in configured_options.items() if key != CONF_PREVENT_OPENING}
        )
        configured_options = new_options
        if requires_reload:
            await hass.config_entries.async_reload(updated_entry.entry_id)
        else:
            coordinator.async_update_listeners()

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_finish_setup(
    hass: HomeAssistant,
    entry: SiegeniaConfigEntry,
    coordinator: SiegeniaDataUpdateCoordinator,
) -> None:
    """Finish setup after early shutdown ownership has been registered."""

    try:
        await coordinator.async_setup()
    except ConfigEntryAuthFailed:
        # Wrong credentials should still trigger HA's reauth flow.
        raise
    except Exception as exc:  # noqa: BLE001
        # Keep loading the integration while the device is offline.
        coordinator.logger.warning("Initial connection failed; will retry in background: %s", exc)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        # Wrong credentials should still trigger HA's reauth flow.
        raise
    except Exception as exc:  # noqa: BLE001
        # The failed refresh marks coordinator entities unavailable until recovery.
        coordinator.logger.warning("Initial refresh failed; will retry in background: %s", exc)

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

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SiegeniaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_migrate_devices(hass: HomeAssistant, entry: SiegeniaConfigEntry) -> None:
    serial = entry.data.get(CONF_SERIAL) or entry.unique_id
    host = entry.data.get(CONF_HOST)
    await async_merge_devices(hass, entry.entry_id, serial=serial, host=host)


async def async_remove_entry(hass: HomeAssistant, entry: SiegeniaConfigEntry) -> None:
    """Remove the deleted controller's connection warning."""
    async_clear_connection_issue(hass, entry.entry_id)
