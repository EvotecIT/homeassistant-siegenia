from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.siegenia.const import DOMAIN
from custom_components.siegenia.coordinator import SiegeniaDataUpdateCoordinator


async def test_setup_stays_loaded_and_unavailable_while_device_is_offline(
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


async def test_transient_reconnect_login_failure_closes_socket_before_retry(
    hass,
    config_entry_data,
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
                raise OSError("transient login timeout")

        async def start_heartbeat(self, interval: int) -> None:
            self.heartbeat_calls += 1

        async def disconnect(self) -> None:
            self.disconnect_calls += 1
            self.connected = False

    client = _RecoveringClient()
    coordinator.client = client  # type: ignore[assignment]

    with pytest.raises(UpdateFailed):
        await coordinator._ensure_connected()

    assert client.connected is False
    assert client.disconnect_calls == 1

    await coordinator._ensure_connected()

    assert client.connected is True
    assert client.login_attempts == 2
    assert client.heartbeat_calls == 1
