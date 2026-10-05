from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
try:
    # Newer HA
    from homeassistant.data_entry_flow import FlowResultType as _FlowResultType  # type: ignore
    _CREATE = _FlowResultType.CREATE_ENTRY
except Exception:  # noqa: BLE001
    _FlowResultType = None
    _CREATE = "create_entry"

from custom_components.siegenia.const import (
    CONF_ENABLE_BUTTONS,
    CONF_DEBUG,
    CONF_ENABLE_OPEN_COUNT,
    CONF_ENABLE_POSITION_SLIDER,
    CONF_ENABLE_STATE_SENSOR,
    CONF_HEARTBEAT_INTERVAL,
    CONF_IDLE_INTERVAL,
    CONF_INFORMATIONAL,
    CONF_MOTION_INTERVAL,
    CONF_POLL_INTERVAL,
    CONF_PREVENT_OPENING,
    CONF_SLIDER_CWOL_MAX,
    CONF_SLIDER_GAP_MAX,
    CONF_SLIDER_STOP_OVER_DISPLAY,
    CONF_VERIFY_SSL,
    CONF_WARNING_EVENTS,
    CONF_WARNING_NOTIFICATIONS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from custom_components.siegenia.api import AuthenticationError


async def test_user_flow_success(hass, monkeypatch, mock_client):
    # Mock client factory in conftest creates a working client
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    user_input = {
        "host": "192.0.2.1",
        "username": "admin",
        "password": "pw",
        "port": 443,
        "ws_protocol": "wss",
        "poll_interval": 5,
        "heartbeat_interval": 10,
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=user_input)
    await hass.async_block_till_done()
    # Works on both old and new HA versions
    assert result2["type"] == _CREATE or result2["type"] == "create_entry"
    assert result2["title"] == "Siegenia Test"
    assert result2["data"]["host"] == "192.0.2.1"
    assert result2["data"][CONF_VERIFY_SSL] is DEFAULT_VERIFY_SSL


async def test_user_flow_uses_ws_protocol(hass, monkeypatch, mock_client):
    session = object()
    calls = {}

    def _factory(*args, **kwargs):  # noqa: ANN001, ANN002
        from unittest.mock import AsyncMock

        calls["ws_protocol"] = kwargs.get("ws_protocol")
        calls["session"] = kwargs.get("session")
        calls["verify_ssl"] = kwargs.get("verify_ssl")

        class _C:
            connect = AsyncMock()
            disconnect = AsyncMock()
            login = AsyncMock()
            get_device = AsyncMock(
                return_value={
                    "status": "ok",
                    "data": {"devicename": "Siegenia Test", "serialnr": "00112233"},
                }
            )

        return _C()

    monkeypatch.setattr("custom_components.siegenia.api.SiegeniaClient", _factory)
    monkeypatch.setattr("custom_components.siegenia.config_flow.SiegeniaClient", _factory)
    monkeypatch.setattr("custom_components.siegenia.config_flow.async_get_clientsession", lambda hass: session)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    user_input = {
        "host": "192.0.2.1",
        "username": "admin",
        "password": "pw",
        "port": 443,
        "ws_protocol": "ws",
        CONF_VERIFY_SSL: True,
        "poll_interval": 5,
        "heartbeat_interval": 10,
    }
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=user_input)
    await hass.async_block_till_done()
    assert result2["type"] == _CREATE or result2["type"] == "create_entry"
    assert calls["ws_protocol"] == "ws"
    assert calls["session"] is session
    assert calls["verify_ssl"] is True


async def test_user_flow_auth_error(hass, monkeypatch):
    # Patch login to raise AuthenticationError
    def _factory(*args, **kwargs):  # noqa: ANN001, ANN002
        from unittest.mock import AsyncMock

        class _C:
            connect = AsyncMock()
            disconnect = AsyncMock()
            get_device = AsyncMock()
            login = AsyncMock(side_effect=AuthenticationError("authentication_error"))

        return _C()

    # Patch both api and the symbol imported into config_flow
    monkeypatch.setattr("custom_components.siegenia.api.SiegeniaClient", _factory)
    monkeypatch.setattr("custom_components.siegenia.config_flow.SiegeniaClient", _factory)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"host": "1.2.3.4", "username": "a", "password": "b", "port": 443, "ws_protocol": "wss", "poll_interval": 5, "heartbeat_interval": 10},
    )
    assert result2["type"] == "form"
    assert result2["errors"]["base"] == "auth"


async def test_reauth_uses_ws_protocol(hass, monkeypatch, mock_client):
    session = object()
    calls = {}

    def _factory(*args, **kwargs):  # noqa: ANN001, ANN002
        from unittest.mock import AsyncMock

        calls["ws_protocol"] = kwargs.get("ws_protocol")
        calls["session"] = kwargs.get("session")
        calls["verify_ssl"] = kwargs.get("verify_ssl")

        class _C:
            connect = AsyncMock()
            disconnect = AsyncMock()
            login = AsyncMock()

        return _C()

    monkeypatch.setattr("custom_components.siegenia.api.SiegeniaClient", _factory)
    monkeypatch.setattr("custom_components.siegenia.config_flow.SiegeniaClient", _factory)
    monkeypatch.setattr("custom_components.siegenia.config_flow.async_get_clientsession", lambda hass: session)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.0.2.1",
            "port": 443,
            "username": "admin",
            "password": "pw",
            "ws_protocol": "ws",
            CONF_VERIFY_SSL: True,
        },
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"username": "admin", "password": "pw"}
    )
    assert result2["type"] == "abort"
    assert calls["ws_protocol"] == "ws"
    assert calls["session"] is session
    assert calls["verify_ssl"] is True


async def test_options_flow_uses_framework_config_entry(hass, config_entry_data):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "general"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "general"

    # Individually valid values can still contradict the slider ordering.
    invalid_options = result["data_schema"]({})
    invalid_options[CONF_SLIDER_GAP_MAX] = 60
    invalid_options[CONF_SLIDER_CWOL_MAX] = 50
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=invalid_options
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_thresholds"
    assert not entry.options

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_POLL_INTERVAL: 10,
            CONF_HEARTBEAT_INTERVAL: 20,
            CONF_ENABLE_POSITION_SLIDER: True,
            CONF_ENABLE_OPEN_COUNT: True,
            CONF_ENABLE_STATE_SENSOR: True,
            CONF_DEBUG: False,
            CONF_INFORMATIONAL: False,
            CONF_WARNING_NOTIFICATIONS: True,
            CONF_WARNING_EVENTS: True,
            CONF_ENABLE_BUTTONS: False,
            CONF_MOTION_INTERVAL: 2,
            CONF_IDLE_INTERVAL: 60,
            CONF_PREVENT_OPENING: True,
            CONF_SLIDER_GAP_MAX: 10,
            CONF_SLIDER_CWOL_MAX: 50,
            CONF_SLIDER_STOP_OVER_DISPLAY: 90,
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options[CONF_PREVENT_OPENING] is True

    reopened = await hass.config_entries.options.async_init(entry.entry_id)
    reopened = await hass.config_entries.options.async_configure(
        reopened["flow_id"], user_input={"next_step_id": "general"}
    )
    defaults = reopened["data_schema"]({})
    assert defaults[CONF_POLL_INTERVAL] == 10
    assert defaults[CONF_HEARTBEAT_INTERVAL] == 20


async def test_connection_options_update_the_selected_entry(hass, config_entry_data, monkeypatch):
    from unittest.mock import AsyncMock

    entry = MockConfigEntry(domain=DOMAIN, data=config_entry_data, title="Siegenia Test")
    entry.add_to_hass(hass)
    reload_entry = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload_entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "connection"}
    )
    assert result["type"] == "form"
    options = result["data_schema"]({"password": "new-password"})
    options["host"] = "192.0.2.22"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=options
    )
    assert result["type"] == "abort"
    assert result["reason"] == "reconfigured"
    assert entry.data["host"] == "192.0.2.22"
    assert entry.data["password"] == "new-password"
    reload_entry.assert_awaited_once_with(entry.entry_id)


async def test_saved_general_options_reload_the_running_entry(hass, setup_integration):
    entry = setup_integration
    previous = hass.data[DOMAIN][entry.entry_id]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "general"}
    )
    options = result["data_schema"]({})
    options[CONF_PREVENT_OPENING] = not previous.prevent_opening
    options[CONF_POLL_INTERVAL] = 12
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=options
    )
    await hass.async_block_till_done()
    current = hass.data[DOMAIN][entry.entry_id]
    assert result["type"] == "create_entry"
    assert current is not previous
    assert previous._stopping is True
    assert current.prevent_opening is options[CONF_PREVENT_OPENING]
    assert current._default_interval.total_seconds() == 12

    # Host/identity data updates must not cause a second reload from this listener.
    hass.config_entries.async_update_entry(entry, data={**entry.data, "host": "192.0.2.33"})
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is current
