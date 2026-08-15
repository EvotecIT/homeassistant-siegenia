from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.siegenia import async_setup_entry
from custom_components.siegenia.const import DOMAIN
from custom_components.siegenia.coordinator import SiegeniaDataUpdateCoordinator


async def test_home_assistant_stop_disconnects_client(
    hass,
    monkeypatch,
    mock_client,
    config_entry_data,
) -> None:
    stop_listeners = []
    event_bus_type = type(hass.bus)
    async_listen_once = event_bus_type.async_listen_once

    def capture_listener(self, event_type, listener):
        if (
            event_type == EVENT_HOMEASSISTANT_STOP
            and listener.__name__ == "_async_shutdown_on_stop"
        ):
            stop_listeners.append(listener)
        return async_listen_once(self, event_type, listener)

    monkeypatch.setattr(event_bus_type, "async_listen_once", capture_listener)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(stop_listeners) == 1
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.client.disconnect.reset_mock()

    await stop_listeners[0](Mock())

    coordinator.client.disconnect.assert_awaited_once_with()


async def test_failed_setup_disconnects_client(
    hass,
    monkeypatch,
    mock_client,
    config_entry_data,
) -> None:
    monkeypatch.setattr(
        "custom_components.siegenia.async_setup_services",
        AsyncMock(side_effect=RuntimeError("service setup failed")),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.client.disconnect.assert_awaited_once_with()


async def test_cancelled_setup_disconnects_client(
    hass,
    monkeypatch,
    mock_client,
    config_entry_data,
) -> None:
    monkeypatch.setattr(
        "custom_components.siegenia.async_setup_services",
        AsyncMock(side_effect=asyncio.CancelledError()),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)

    with pytest.raises(asyncio.CancelledError):
        await async_setup_entry(hass, entry)

    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.client.disconnect.assert_awaited_once_with()


async def test_shutdown_cancels_inflight_connection_before_tasks_start(
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
    connect_started = asyncio.Event()
    login_calls = 0
    heartbeat_calls = 0
    disconnect_calls = 0

    class _ConnectingClient:
        connected = False

        async def connect(self) -> None:
            connect_started.set()
            await asyncio.Event().wait()

        async def login(self, username: str, password: str) -> None:
            nonlocal login_calls
            login_calls += 1

        async def start_heartbeat(self, interval: int) -> None:
            nonlocal heartbeat_calls
            heartbeat_calls += 1

        async def disconnect(self) -> None:
            nonlocal disconnect_calls
            disconnect_calls += 1

    coordinator.client = _ConnectingClient()  # type: ignore[assignment]
    setup_task = asyncio.create_task(coordinator.async_setup())
    await connect_started.wait()

    await asyncio.wait_for(coordinator.async_shutdown(), timeout=1)

    with pytest.raises(asyncio.CancelledError):
        await setup_task
    assert login_calls == 0
    assert heartbeat_calls == 0
    assert disconnect_calls == 1

    with pytest.raises(asyncio.CancelledError):
        await coordinator._ensure_connected()
