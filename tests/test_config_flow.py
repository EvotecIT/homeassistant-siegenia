import pytest

from homeassistant import config_entries
try:
    # Newer HA
    from homeassistant.data_entry_flow import FlowResultType as _FlowResultType  # type: ignore
    _CREATE = _FlowResultType.CREATE_ENTRY
except Exception:  # noqa: BLE001
    _FlowResultType = None
    _CREATE = "create_entry"

from custom_components.siegenia.const import DOMAIN
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


async def test_user_flow_uses_ws_protocol(hass, monkeypatch):
    calls = {}

    def _factory(*args, **kwargs):  # noqa: ANN001, ANN002
        from unittest.mock import AsyncMock

        calls["ws_protocol"] = kwargs.get("ws_protocol")

        class _C:
            connect = AsyncMock()
            disconnect = AsyncMock()
            login = AsyncMock()
            get_device = AsyncMock(
                return_value={
                    "status": "ok",
                    "data": {"devicename": "Siegenia Test", "serialnr": "af050261"},
                }
            )

        return _C()

    monkeypatch.setattr("custom_components.siegenia.api.SiegeniaClient", _factory)
    monkeypatch.setattr("custom_components.siegenia.config_flow.SiegeniaClient", _factory)

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
        "poll_interval": 5,
        "heartbeat_interval": 10,
    }
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=user_input)
    await hass.async_block_till_done()
    assert result2["type"] == _CREATE or result2["type"] == "create_entry"
    assert calls["ws_protocol"] == "ws"


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


async def test_reauth_uses_ws_protocol(hass, monkeypatch):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    calls = {}

    def _factory(*args, **kwargs):  # noqa: ANN001, ANN002
        from unittest.mock import AsyncMock

        calls["ws_protocol"] = kwargs.get("ws_protocol")

        class _C:
            connect = AsyncMock()
            disconnect = AsyncMock()
            login = AsyncMock()

        return _C()

    monkeypatch.setattr("custom_components.siegenia.api.SiegeniaClient", _factory)
    monkeypatch.setattr("custom_components.siegenia.config_flow.SiegeniaClient", _factory)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.0.2.1", "port": 443, "username": "admin", "password": "pw", "ws_protocol": "ws"},
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
