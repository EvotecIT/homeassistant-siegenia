from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA as TRIGGER_BASE_SCHEMA,
)
from homeassistant.components.homeassistant.triggers import state as _state_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo

from .const import DOMAIN

TRIGGER_TYPES = {
    "opened": {"entity_suffix": "_window_state", "to": "open"},
    "closed": {"entity_suffix": "_window_state", "to": "closed"},
    "gap_vent": {"entity_suffix": "_window_state", "to": "gap_vent"},
    "closed_wo_lock": {"entity_suffix": "_window_state", "to": "closed_wo_lock"},
    "stop_over": {"entity_suffix": "_window_state", "to": "stop_over"},
    "moving_started": {"entity_suffix": "_moving", "legacy_suffix": "_window_moving", "to": "on"},
    "moving_stopped": {"entity_suffix": "_moving", "legacy_suffix": "_window_moving", "to": "off"},
    "warning_active": {"entity_suffix": "_warning_active", "to": "on"},
    "warning_cleared": {"entity_suffix": "_warning_active", "to": "off"},
}


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    triggers: list[dict[str, Any]] = []
    ent_reg = er.async_get(hass)
    for entry in er.async_entries_for_device(ent_reg, device_id):
        if entry.domain not in {"sensor", "binary_sensor"}:
            continue
        for t, meta in TRIGGER_TYPES.items():
            suffix = meta["entity_suffix"]
            legacy = meta.get("legacy_suffix")
            if entry.entity_id.endswith(suffix) or (legacy and entry.entity_id.endswith(legacy)):
                triggers.append(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: t,
                    }
                )
    return triggers


TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(list(TRIGGER_TYPES.keys())),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: dict[str, Any],
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    config = TRIGGER_SCHEMA(config)
    meta = TRIGGER_TYPES[config[CONF_TYPE]]
    state_config = {
        CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        "to": meta["to"],
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]
    state_config = await _state_trigger.async_validate_trigger_config(hass, state_config)
    return await _state_trigger.async_attach_trigger(hass, state_config, action, trigger_info, platform_type="device")
