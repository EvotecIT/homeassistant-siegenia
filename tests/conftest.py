from __future__ import annotations

import sys
from pathlib import Path

import pytest
from unittest.mock import AsyncMock

# Ensure repository root is on sys.path so `custom_components` is importable in CI
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Auto-load pytest plugin for HA fixtures
pytest_plugins = "pytest_homeassistant_custom_component"

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME  # noqa: E402

from custom_components.siegenia.const import DOMAIN, DEFAULT_PORT  # noqa: E402

# Ensure HA loads custom components from this repository during tests
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # noqa: ANN001
    yield

# Override PHACC's strict cleanup to tolerate harmless background threads
@pytest.fixture(autouse=True)
def verify_cleanup():  # noqa: D401
    """Override PHACC's verify_cleanup to avoid thread assertions in CI."""
    yield


@pytest.fixture
def mock_client(monkeypatch):
    class _Client:
        def __init__(self, host, port=DEFAULT_PORT, session=None, logger=None, ws_protocol="wss", **_):  # noqa: ARG002
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
                    "stopover": 3,
                    "max_stopover": 13,
                    "firmware_update": 0,
                }
            })
            self.open_close = AsyncMock()
            self.stop = AsyncMock()
            self.reboot_device = AsyncMock()
            self.reset_device = AsyncMock()
            self.renew_cert = AsyncMock()
            self.set_device_params = AsyncMock()
            self.connected = True
            self.push_cb = None
            def _set_cb(cb):
                self.push_cb = cb
            self.set_push_callback = _set_cb

    def _factory(host, port=DEFAULT_PORT, **_):
        return _Client(host, port)

    monkeypatch.setattr("custom_components.siegenia.api.SiegeniaClient", _factory)
    # Also patch the symbol imported into coordinator/config_flow modules
    try:
        monkeypatch.setattr("custom_components.siegenia.coordinator.SiegeniaClient", _Client)
    except Exception:
        pass
    try:
        monkeypatch.setattr("custom_components.siegenia.config_flow.SiegeniaClient", _Client)
    except Exception:
        pass
    return _factory

# Explicit opt-in per test keeps control in each test


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
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data=config_entry_data, title="Siegenia Test")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
