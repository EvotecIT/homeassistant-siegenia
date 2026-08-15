from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.siegenia import async_setup_entry
from custom_components.siegenia.const import DOMAIN


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
