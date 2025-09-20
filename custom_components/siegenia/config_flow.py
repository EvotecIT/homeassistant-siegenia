from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .api import SiegeniaClient, AuthenticationError
from .const import (
    CONF_HEARTBEAT_INTERVAL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_USERNAME,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_WS_PROTOCOL,
    DOMAIN,
    CONF_WS_PROTOCOL,
    CONF_ENABLE_POSITION_SLIDER,
    CONF_ENABLE_OPEN_COUNT,
    CONF_ENABLE_STATE_SENSOR,
    CONF_DEBUG,
    CONF_INFORMATIONAL,
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_WS_PROTOCOL, default=DEFAULT_WS_PROTOCOL): vol.In(["wss", "ws"]),
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
        vol.Optional(CONF_HEARTBEAT_INTERVAL, default=DEFAULT_HEARTBEAT_INTERVAL): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # Try to connect and fetch device info
        client = SiegeniaClient(host, port=port)
        try:
            await client.connect()
            await client.login(username, password)
            info = await client.get_device()
        except AuthenticationError:
            errors["base"] = "auth"
        except Exception:  # noqa: BLE001
            errors["base"] = "cannot_connect"
        finally:
            await client.disconnect()

        if errors:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)

        # Use serial number as unique_id
        serial = (info.get("data") or {}).get("serialnr") or host
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        title = (info.get("data") or {}).get("devicename") or f"Siegenia {host}"
        return self.async_create_entry(title=title, data=user_input)

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:  # For YAML import (not used)
        return await self.async_step_user(import_config)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = {
            CONF_POLL_INTERVAL: self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            CONF_HEARTBEAT_INTERVAL: self.config_entry.data.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL),
            CONF_ENABLE_POSITION_SLIDER: self.config_entry.options.get(CONF_ENABLE_POSITION_SLIDER, True),
            CONF_ENABLE_OPEN_COUNT: self.config_entry.options.get(CONF_ENABLE_OPEN_COUNT, True),
            CONF_ENABLE_STATE_SENSOR: self.config_entry.options.get(CONF_ENABLE_STATE_SENSOR, True),
            CONF_DEBUG: self.config_entry.options.get(CONF_DEBUG, False),
            CONF_INFORMATIONAL: self.config_entry.options.get(CONF_INFORMATIONAL, False),
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_POLL_INTERVAL, default=data[CONF_POLL_INTERVAL]): int,
                vol.Required(CONF_HEARTBEAT_INTERVAL, default=data[CONF_HEARTBEAT_INTERVAL]): int,
                vol.Required(CONF_ENABLE_POSITION_SLIDER, default=data[CONF_ENABLE_POSITION_SLIDER]): bool,
                vol.Required(CONF_ENABLE_OPEN_COUNT, default=data[CONF_ENABLE_OPEN_COUNT]): bool,
                vol.Required(CONF_ENABLE_STATE_SENSOR, default=data[CONF_ENABLE_STATE_SENSOR]): bool,
                vol.Required(CONF_DEBUG, default=data[CONF_DEBUG]): bool,
                vol.Required(CONF_INFORMATIONAL, default=data[CONF_INFORMATIONAL]): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


async def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlowHandler:
    return OptionsFlowHandler(config_entry)

