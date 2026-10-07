from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.siegenia.const import DOMAIN
from custom_components.siegenia.coordinator import SiegeniaDataUpdateCoordinator
from custom_components.siegenia.siegenia_client.client import AuthenticationError


async def test_offline_setup_recovers_on_scheduled_refresh(
    hass,
    monkeypatch,
    config_entry_data,
) -> None:
    class _OfflineClient:
        connected = False

        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            self.connect = AsyncMock(side_effect=OSError("offline"))
            self.disconnect = AsyncMock()
            self.login = AsyncMock()
            self.start_heartbeat = AsyncMock()
            self.get_device_params = AsyncMock(return_value={
                "status": "ok", "data": {"states": {"0": "CLOSED"}, "warnings": []},
            })

        def set_push_callback(self, callback) -> None:  # noqa: ANN001
            return None

    monkeypatch.setattr(
        "custom_components.siegenia.coordinator.SiegeniaClient",
        _OfflineClient,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**config_entry_data, "auto_discover": False},
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cover = next(
        state
        for state in hass.states.async_all("cover")
        if state.entity_id.endswith("_window")
    )
    assert cover.state == "unavailable"

    coordinator = entry.runtime_data
    client = coordinator.client

    async def connect():
        client.connected = True

    client.connect.side_effect = connect
    client.login.reset_mock()
    client.start_heartbeat.reset_mock()
    assert coordinator.update_interval is not None
    async_fire_time_changed(hass, dt_util.utcnow() + coordinator.update_interval + timedelta(seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(cover.entity_id).state == "closed"
    client.login.assert_awaited_once()
    client.start_heartbeat.assert_awaited_once()
    client.get_device_params.assert_awaited_once()


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        (OSError("transient login timeout"), UpdateFailed),
        (asyncio.CancelledError(), asyncio.CancelledError),
        (AuthenticationError("invalid_credentials"), ConfigEntryAuthFailed),
        (ValueError("invalid login response"), UpdateFailed),
    ],
)
async def test_reconnect_login_failure_closes_socket_before_retry(
    hass,
    config_entry_data,
    failure,
    expected_error,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)
    coordinator = SiegeniaDataUpdateCoordinator(
        hass,
        entry=entry,
        host=config_entry_data["host"],
        port=config_entry_data["port"],
        username=config_entry_data["username"],
        password=config_entry_data["password"],
        auto_discover=False,
    )

    class _RecoveringClient:
        def __init__(self) -> None:
            self.connected = False
            self.login_attempts = 0
            self.disconnect_calls = 0
            self.heartbeat_calls = 0

        async def connect(self) -> None:
            self.connected = True

        async def login(self, username: str, password: str) -> None:
            self.login_attempts += 1
            if self.login_attempts == 1:
                raise failure

        async def start_heartbeat(self, interval: int) -> None:
            self.heartbeat_calls += 1

        async def disconnect(self) -> None:
            self.disconnect_calls += 1
            self.connected = False

    client = _RecoveringClient()
    coordinator.client = client  # type: ignore[assignment]

    with pytest.raises(expected_error):
        await coordinator._ensure_connected()

    assert client.connected is False
    assert client.disconnect_calls == 1

    await coordinator._ensure_connected()

    assert client.connected is True
    assert client.login_attempts == 2
    assert client.heartbeat_calls == 1
