from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_HEARTBEAT_INTERVAL,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_USERNAME,
    CONF_HOST,
    PLATFORMS,
)
from .coordinator import SiegeniaDataUpdateCoordinator
from .__init_services__ import async_setup_services


type SiegeniaConfigEntry = ConfigEntry[SiegeniaDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    coordinator = SiegeniaDataUpdateCoordinator(
        hass,
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        poll_interval=data.get(CONF_POLL_INTERVAL),
        heartbeat_interval=data.get(CONF_HEARTBEAT_INTERVAL),
    )

    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(entry.domain, {})[entry.entry_id] = coordinator

    # Register services once per HA instance using a marker
    marker = f"{DOMAIN}_services_registered"
    if not hass.data.get(marker):
        await async_setup_services(hass)
        hass.data[marker] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: SiegeniaDataUpdateCoordinator = hass.data[entry.domain].pop(entry.entry_id)
    await coordinator.client.disconnect()
    return unload_ok
