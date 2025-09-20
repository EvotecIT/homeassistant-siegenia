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
    CONF_WARNING_NOTIFICATIONS,
    CONF_WARNING_EVENTS,
    CONF_SLIDER_GAP_MAX,
    CONF_SLIDER_CWOL_MAX,
    CONF_SLIDER_STOP_OVER_DISPLAY,
    DEFAULT_GAP_MAX,
    DEFAULT_CWOL_MAX,
    DEFAULT_STOP_OVER_DISPLAY,
    CONF_ENABLE_BUTTONS,
    CONF_MOTION_INTERVAL,
    CONF_IDLE_INTERVAL,
    DEFAULT_MOTION_INTERVAL,
    DEFAULT_IDLE_INTERVAL,
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

    async def async_step_reauth(self, data: dict[str, Any] | None = None) -> FlowResult:
        # Store existing
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context.get("entry_id"))
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])  # type: ignore[index]
        assert entry is not None
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME)): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            )
            return self.async_show_form(step_id="reauth_confirm", data_schema=schema)

        # Try new credentials
        client = SiegeniaClient(entry.data[CONF_HOST], port=entry.data.get(CONF_PORT, DEFAULT_PORT))
        try:
            await client.connect()
            await client.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        except AuthenticationError:
            errors["base"] = "auth"
        except Exception:
            errors["base"] = "cannot_connect"
        finally:
            await client.disconnect()

        if errors:
            schema = vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME)): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            )
            return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)

        # Save back to entry
        new_data = dict(entry.data)
        new_data[CONF_USERNAME] = user_input[CONF_USERNAME]
        new_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
        self.hass.config_entries.async_update_entry(entry, data=new_data)
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        # Show a simple menu to pick what to configure
        if user_input is None:
            return self.async_show_menu(
                step_id="init",
                menu_options=["general", "connection"],
            )
        # Fallback
        return await self.async_step_general()

    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> FlowResult:
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
            CONF_WARNING_NOTIFICATIONS: self.config_entry.options.get(CONF_WARNING_NOTIFICATIONS, True),
            CONF_WARNING_EVENTS: self.config_entry.options.get(CONF_WARNING_EVENTS, True),
            CONF_ENABLE_BUTTONS: self.config_entry.options.get(CONF_ENABLE_BUTTONS, False),
            CONF_MOTION_INTERVAL: self.config_entry.options.get(CONF_MOTION_INTERVAL, DEFAULT_MOTION_INTERVAL),
            CONF_IDLE_INTERVAL: self.config_entry.options.get(CONF_IDLE_INTERVAL, DEFAULT_IDLE_INTERVAL),
            CONF_SLIDER_GAP_MAX: self.config_entry.options.get(CONF_SLIDER_GAP_MAX, DEFAULT_GAP_MAX),
            CONF_SLIDER_CWOL_MAX: self.config_entry.options.get(CONF_SLIDER_CWOL_MAX, DEFAULT_CWOL_MAX),
            CONF_SLIDER_STOP_OVER_DISPLAY: self.config_entry.options.get(CONF_SLIDER_STOP_OVER_DISPLAY, DEFAULT_STOP_OVER_DISPLAY),
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
                vol.Required(CONF_WARNING_NOTIFICATIONS, default=data[CONF_WARNING_NOTIFICATIONS]): bool,
                vol.Required(CONF_WARNING_EVENTS, default=data[CONF_WARNING_EVENTS]): bool,
                vol.Required(CONF_ENABLE_BUTTONS, default=data[CONF_ENABLE_BUTTONS]): bool,
                vol.Required(CONF_MOTION_INTERVAL, default=data[CONF_MOTION_INTERVAL]): vol.All(int, vol.Range(min=1, max=10)),
                vol.Required(CONF_IDLE_INTERVAL, default=data[CONF_IDLE_INTERVAL]): vol.All(int, vol.Range(min=10, max=600)),
                vol.Required(CONF_SLIDER_GAP_MAX, default=data[CONF_SLIDER_GAP_MAX]): vol.All(int, vol.Range(min=1, max=99)),
                vol.Required(CONF_SLIDER_CWOL_MAX, default=data[CONF_SLIDER_CWOL_MAX]): vol.All(int, vol.Range(min=1, max=99)),
                vol.Required(CONF_SLIDER_STOP_OVER_DISPLAY, default=data[CONF_SLIDER_STOP_OVER_DISPLAY]): vol.All(int, vol.Range(min=1, max=99)),
            }
        )

        errors: dict[str, str] = {}
        if user_input is not None:
            gap = user_input[CONF_SLIDER_GAP_MAX]
            cwol = user_input[CONF_SLIDER_CWOL_MAX]
            if not (0 < gap < cwol < 100):
                errors["base"] = "invalid_thresholds"
                return self.async_show_form(step_id="general", data_schema=schema, errors=errors)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="general", data_schema=schema)

    async def async_step_connection(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        # Allow changing connection params + credentials
        d = self.config_entry.data
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_HOST, default=d.get(CONF_HOST)): str,
                    vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): int,
                    vol.Required(CONF_WS_PROTOCOL, default=d.get(CONF_WS_PROTOCOL, DEFAULT_WS_PROTOCOL)): vol.In(["wss", "ws"]),
                    vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME)): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            )
            return self.async_show_form(step_id="connection", data_schema=schema)

        # Update entry.data and reload
        new_data = dict(self.config_entry.data)
        new_data.update(
            {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_WS_PROTOCOL: user_input[CONF_WS_PROTOCOL],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
        )
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        return self.async_abort(reason="reconfigured")


async def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlowHandler:
    return OptionsFlowHandler(config_entry)
