import pytest
from unittest.mock import AsyncMock

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from custom_components.siegenia.const import DOMAIN, DEFAULT_PORT


@pytest.fixture
def mock_client(monkeypatch):
    class _Client:
        def __init__(self, host, port=DEFAULT_PORT, session=None, logger=None):  # noqa: ARG002
            self.host = host
            self.port = port
            # Async methods mocked
            self.connect = AsyncMock()
            self.disconnect = AsyncMock()
            self.login = AsyncMock()
            self.start_heartbeat = AsyncMock()
            self.get_device = AsyncMock(return_value={
                "status": "ok",
                "data": {
                    "devicename": "Siegenia Test",
                    "serialnr": "af050261",
                    "type": 6,
                    "softwareversion": "1.7.2",
                    "hardwareversion": "1.2",
                }
            })
            self.get_device_params = AsyncMock(return_value={
                "status": "ok",
                "data": {
                    "states": {"0": "CLOSED"},
                    "warnings": [],
                }
            })
            self.open_close = AsyncMock()
            self.stop = AsyncMock()
            self.reboot_device = AsyncMock()
            self.reset_device = AsyncMock()
            self.renew_cert = AsyncMock()
            self.connected = True

    def _factory(host, port=DEFAULT_PORT, **_):
        return _Client(host, port)

    monkeypatch.setattr("custom_components.siegenia.api.SiegeniaClient", _factory)
    return _factory


@pytest.fixture
def config_entry_data():
    return {
        CONF_HOST: "192.0.2.1",
        CONF_PORT: 443,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
    }


@pytest.fixture
async def setup_integration(hass, mock_client, config_entry_data):  # noqa: ARG001
    entry = hass.config_entries.async_create_entry(domain=DOMAIN, data=config_entry_data, title="Siegenia Test")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry

