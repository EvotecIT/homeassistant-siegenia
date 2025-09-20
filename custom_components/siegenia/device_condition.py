from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.components.homeassistant.condition import state as StateCondition
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_ENTITY_ID, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN


CONDITION_TYPES = {
    "is_open": {"entity_suffix": "_window_state", "state": "OPEN"},
    "is_closed": {"entity_suffix": "_window_state", "state": "CLOSED"},
    "is_gap_vent": {"entity_suffix": "_window_state", "state": "GAP_VENT"},
    "is_closed_wo_lock": {"entity_suffix": "_window_state", "state": "CLOSED_WO_LOCK"},
    "is_stop_over": {"entity_suffix": "_window_state", "state": "STOP_OVER"},
    "is_moving": {"entity_suffix": "_window_moving", "state": "on"},
    "warning_active": {"entity_suffix": "_warning_active", "state": "on"},
}


async def async_get_conditions(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    ent_reg = er.async_get(hass)
    for entry in er.async_entries_for_device(ent_reg, device_id):
        if entry.domain not in {"sensor", "binary_sensor"}:
            continue
        for t, meta in CONDITION_TYPES.items():
            if entry.entity_id.endswith(meta["entity_suffix"]):
                conditions.append(
                    {
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: t,
                    }
                )
    return conditions


CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(list(CONDITION_TYPES.keys())),
    }
)


async def async_condition_from_config(hass: HomeAssistant, config: dict) -> StateCondition:
    config = CONDITION_SCHEMA(config)
    meta = CONDITION_TYPES[config[CONF_TYPE]]
    return StateCondition(hass, {CONF_ENTITY_ID: config[CONF_ENTITY_ID], "state": meta["state"]})

