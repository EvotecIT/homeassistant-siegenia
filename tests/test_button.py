"""Optional controls route HA button presses through the shared command policy."""

import pytest

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.siegenia.const import (
    CONF_ENABLE_BUTTONS,
    CONF_PREVENT_OPENING,
    DOMAIN,
)


async def test_buttons_require_opt_in(hass, setup_integration):
    registry = er.async_get(hass)
    assert not [
        entry for entry in registry.entities.values()
        if entry.config_entry_id == setup_integration.entry_id
        and entry.domain == "button"
    ]


async def test_enabled_buttons_route_commands_and_respect_opening_lock(
    hass, mock_client, config_entry_data,
):
    entry = MockConfigEntry(
        domain=DOMAIN, data=config_entry_data,
        options={CONF_ENABLE_BUTTONS: True}, title="Siegenia Test",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    buttons = {
        item.unique_id.removeprefix("00112233-button-"): item.entity_id
        for item in registry.entities.values()
        if item.config_entry_id == entry.entry_id and item.domain == "button"
    }
    expected = {
        "open": "OPEN", "close": "CLOSE", "gap_vent": "GAP_VENT",
        "close_wo_lock": "CLOSE_WO_LOCK", "stop_over": "STOP_OVER", "stop": "STOP",
    }
    assert buttons.keys() == expected.keys()
    client = entry.runtime_data.client
    for key, command in expected.items():
        client.open_close.reset_mock()
        client.stop.reset_mock()
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: buttons[key]}, blocking=True,
        )
        if command == "STOP":
            client.stop.assert_awaited_once_with(0)
            client.open_close.assert_not_awaited()
        else:
            client.open_close.assert_awaited_once_with(0, command)
            client.stop.assert_not_awaited()

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_PREVENT_OPENING: True},
    )
    await hass.async_block_till_done()
    client = entry.runtime_data.client
    client.open_close.reset_mock()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: buttons["open"]}, blocking=True,
        )
    client.open_close.assert_not_awaited()
    client.stop.reset_mock()
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: buttons["stop"]}, blocking=True,
    )
    client.stop.assert_awaited_once_with(0)
