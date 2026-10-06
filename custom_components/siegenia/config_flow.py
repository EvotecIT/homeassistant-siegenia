from __future__ import annotations

from ipaddress import ip_address
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthenticationError, SiegeniaClient
from .const import (
    CONF_AUTO_DISCOVER,
    CONF_DEBUG,
    CONF_ENABLE_BUTTONS,
    CONF_ENABLE_OPEN_COUNT,
    CONF_ENABLE_POSITION_SLIDER,
    CONF_ENABLE_STATE_SENSOR,
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
    CONF_SLIDER_CWOL_MAX,
    CONF_SLIDER_GAP_MAX,
    CONF_SLIDER_STOP_OVER_DISPLAY,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_WARNING_EVENTS,
    CONF_WARNING_NOTIFICATIONS,
    CONF_WS_PROTOCOL,
    DEFAULT_AUTO_DISCOVER,
    DEFAULT_CWOL_MAX,
    DEFAULT_EXTENDED_DISCOVERY,
    DEFAULT_GAP_MAX,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_IDLE_INTERVAL,
    DEFAULT_MOTION_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_PREVENT_OPENING,
    DEFAULT_STOP_OVER_DISPLAY,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WS_PROTOCOL,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_WS_PROTOCOL, default=DEFAULT_WS_PROTOCOL): vol.In(["wss", "ws"]),
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
        vol.Optional(CONF_HEARTBEAT_INTERVAL, default=DEFAULT_HEARTBEAT_INTERVAL): int,
        vol.Optional(CONF_AUTO_DISCOVER, default=DEFAULT_AUTO_DISCOVER): bool,
        vol.Optional(CONF_EXTENDED_DISCOVERY, default=DEFAULT_EXTENDED_DISCOVERY): bool,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OptionsFlowHandler()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # Try to connect and fetch device info
        client = SiegeniaClient(
            host,
            port=port,
            ws_protocol=user_input.get(CONF_WS_PROTOCOL, DEFAULT_WS_PROTOCOL),
            session=async_get_clientsession(self.hass),
            verify_ssl=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
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

        data = dict(user_input)
        data.setdefault(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        data.setdefault(CONF_AUTO_DISCOVER, DEFAULT_AUTO_DISCOVER)
        data.setdefault(CONF_EXTENDED_DISCOVERY, DEFAULT_EXTENDED_DISCOVERY)
        data.setdefault(CONF_SERIAL, serial)
        data["host_based_identity"] = serial == host
        if not data.get(CONF_AUTO_DISCOVER, False):
            data[CONF_EXTENDED_DISCOVERY] = False

        title = (info.get("data") or {}).get("devicename") or f"Siegenia {host}"
        return self.async_create_entry(title=title, data=data)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        return await _async_connection_step(self, entry, user_input, step_id="reconfigure")

    async def async_step_import(self, import_config: dict[str, Any]) -> ConfigFlowResult:  # For YAML import (not used)
        return await self.async_step_user(import_config)

    async def async_step_reauth(self, data: dict[str, Any] | None = None) -> ConfigFlowResult:
        # Store existing
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
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
        client = SiegeniaClient(
            entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
            ws_protocol=entry.data.get(CONF_WS_PROTOCOL, DEFAULT_WS_PROTOCOL),
            session=async_get_clientsession(self.hass),
            verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
        try:
            await client.connect()
            await client.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            info = await client.get_device()
            expected_serial = entry.data.get(CONF_SERIAL) or entry.unique_id
            if expected_serial and not _uses_host_identity(entry):
                if (info.get("data") or {}).get("serialnr") != expected_serial:
                    errors["base"] = "wrong_device"
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
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # Show a simple menu to pick what to configure
        if user_input is None:
            return self.async_show_menu(
                step_id="init",
                menu_options=["general", "connection"],
            )
        # Fallback
        return await self.async_step_general()

    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.handler)
        assert entry is not None
        data = {
            CONF_POLL_INTERVAL: entry.options.get(CONF_POLL_INTERVAL, entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)),
            CONF_HEARTBEAT_INTERVAL: entry.options.get(CONF_HEARTBEAT_INTERVAL, entry.data.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL)),
            CONF_ENABLE_POSITION_SLIDER: entry.options.get(CONF_ENABLE_POSITION_SLIDER, True),
            CONF_ENABLE_OPEN_COUNT: entry.options.get(CONF_ENABLE_OPEN_COUNT, True),
            CONF_ENABLE_STATE_SENSOR: entry.options.get(CONF_ENABLE_STATE_SENSOR, True),
            CONF_DEBUG: entry.options.get(CONF_DEBUG, False),
            CONF_INFORMATIONAL: entry.options.get(CONF_INFORMATIONAL, False),
            CONF_WARNING_NOTIFICATIONS: entry.options.get(CONF_WARNING_NOTIFICATIONS, True),
            CONF_WARNING_EVENTS: entry.options.get(CONF_WARNING_EVENTS, True),
            CONF_ENABLE_BUTTONS: entry.options.get(CONF_ENABLE_BUTTONS, False),
            CONF_MOTION_INTERVAL: entry.options.get(CONF_MOTION_INTERVAL, DEFAULT_MOTION_INTERVAL),
            CONF_IDLE_INTERVAL: entry.options.get(CONF_IDLE_INTERVAL, DEFAULT_IDLE_INTERVAL),
            CONF_PREVENT_OPENING: entry.options.get(CONF_PREVENT_OPENING, DEFAULT_PREVENT_OPENING),
            CONF_SLIDER_GAP_MAX: entry.options.get(CONF_SLIDER_GAP_MAX, DEFAULT_GAP_MAX),
            CONF_SLIDER_CWOL_MAX: entry.options.get(CONF_SLIDER_CWOL_MAX, DEFAULT_CWOL_MAX),
            CONF_SLIDER_STOP_OVER_DISPLAY: entry.options.get(CONF_SLIDER_STOP_OVER_DISPLAY, DEFAULT_STOP_OVER_DISPLAY),
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
                vol.Required(CONF_PREVENT_OPENING, default=data[CONF_PREVENT_OPENING]): bool,
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

    async def async_step_connection(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.handler)
        assert entry is not None
        return await _async_connection_step(self, entry, user_input, step_id="connection")


def _uses_host_identity(entry: config_entries.ConfigEntry) -> bool:
    """Recognize fallback identity without bypassing a subsequently learned serial."""
    expected_serial = entry.data.get(CONF_SERIAL) or entry.unique_id
    host_based_identity = bool(entry.data.get("host_based_identity")) and expected_serial == entry.unique_id
    if expected_serial == entry.data[CONF_HOST]:
        host_based_identity = True
    elif expected_serial:
        # Recognize old IP fallbacks even after the address was changed by a service.
        try:
            ip_address(expected_serial)
        except ValueError:
            pass
        else:
            host_based_identity = True
    return host_based_identity


async def _async_connection_step(
    flow: config_entries.ConfigFlow | config_entries.OptionsFlow,
    entry: config_entries.ConfigEntry,
    user_input: dict[str, Any] | None,
    *,
    step_id: str,
) -> ConfigFlowResult:
    """Validate and save the connection for both HA configuration entry points."""
    # Allow changing connection params + credentials
    d = entry.data
    schema = vol.Schema(
        {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST)): str,
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Required(CONF_WS_PROTOCOL, default=d.get(CONF_WS_PROTOCOL, DEFAULT_WS_PROTOCOL)): vol.In(["wss", "ws"]),
            vol.Required(CONF_VERIFY_SSL, default=d.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)): bool,
            vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME)): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_AUTO_DISCOVER, default=d.get(CONF_AUTO_DISCOVER, DEFAULT_AUTO_DISCOVER)): bool,
            vol.Required(CONF_EXTENDED_DISCOVERY, default=d.get(CONF_EXTENDED_DISCOVERY, DEFAULT_EXTENDED_DISCOVERY)): bool,
        }
    )
    if user_input is None:
        return flow.async_show_form(step_id=step_id, data_schema=schema)

    client = SiegeniaClient(
        user_input[CONF_HOST],
        port=user_input[CONF_PORT],
        ws_protocol=user_input[CONF_WS_PROTOCOL],
        session=async_get_clientsession(flow.hass),
        verify_ssl=user_input[CONF_VERIFY_SSL],
    )
    errors: dict[str, str] = {}
    expected_serial = entry.data.get(CONF_SERIAL) or entry.unique_id
    host_based_identity = _uses_host_identity(entry)
    try:
        await client.connect()
        await client.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        info = await client.get_device()
        if expected_serial and not host_based_identity:
            if (info.get("data") or {}).get("serialnr") != expected_serial:
                errors["base"] = "wrong_device"
    except AuthenticationError:
        errors["base"] = "auth"
    except Exception:  # noqa: BLE001
        errors["base"] = "cannot_connect"
    finally:
        await client.disconnect()
    if errors:
        return flow.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    # Update entry.data and reload
    new_data = dict(entry.data)
    new_data["host_based_identity"] = host_based_identity
    new_data.update(
        {
            CONF_HOST: user_input[CONF_HOST],
            CONF_PORT: user_input[CONF_PORT],
            CONF_WS_PROTOCOL: user_input[CONF_WS_PROTOCOL],
            CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_AUTO_DISCOVER: user_input.get(CONF_AUTO_DISCOVER, DEFAULT_AUTO_DISCOVER),
            CONF_EXTENDED_DISCOVERY: user_input.get(CONF_EXTENDED_DISCOVERY, DEFAULT_EXTENDED_DISCOVERY),
        }
    )
    if not new_data.get(CONF_AUTO_DISCOVER, False):
        new_data[CONF_EXTENDED_DISCOVERY] = False
    flow.hass.config_entries.async_update_entry(entry, data=new_data)
    await flow.hass.config_entries.async_reload(entry.entry_id)
    return flow.async_abort(reason="reconfigured")
