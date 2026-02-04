from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_merge_devices(
    hass: HomeAssistant,
    entry_id: str,
    *,
    serial: str | None = None,
    host: str | None = None,
) -> None:
    """Merge duplicate devices for an entry, keeping the most complete device."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    devices = (
        dev_reg.async_entries_for_config_entry(entry_id)
        if hasattr(dev_reg, "async_entries_for_config_entry")
        else [d for d in dev_reg.devices.values() if entry_id in d.config_entries]
    )
    if not devices:
        return

    primary = None
    if serial:
        primary = next((d for d in devices if (DOMAIN, serial) in d.identifiers), None)
    if primary is None:
        primary = max(devices, key=lambda d: len(d.identifiers))

    if host and (DOMAIN, host) not in primary.identifiers:
        dev_reg.async_update_device(
            primary.id,
            new_identifiers=set(primary.identifiers) | {(DOMAIN, host)},
        )

    for dev in devices:
        if dev.id == primary.id:
            continue
        ents = (
            ent_reg.async_entries_for_device(dev.id)
            if hasattr(ent_reg, "async_entries_for_device")
            else [e for e in ent_reg.entities.values() if e.device_id == dev.id]
        )
        for ent in ents:
            ent_reg.async_update_entity(ent.entity_id, device_id=primary.id)
        try:
            dev_reg.async_remove_device(dev.id)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Failed to remove device %s: %s", dev.id, exc)
