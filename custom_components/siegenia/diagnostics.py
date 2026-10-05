from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.components.diagnostics import async_redact_data

from .models import SiegeniaConfigEntry
from .const import CONF_HOST, CONF_PASSWORD, CONF_SERIAL, CONF_USERNAME

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_HOST,
    CONF_SERIAL,
    "serialnr",
    "devicename",
    "devicelocation",
    "devicefloor",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SiegeniaConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "device_info": coordinator.device_info,
            "last_params": coordinator.data,
        },
        TO_REDACT,
    )
