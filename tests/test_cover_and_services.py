import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import ATTR_ENTITY_ID

from custom_components.siegenia.const import CONF_PREVENT_OPENING, DOMAIN

async def test_cover_commands(hass, setup_integration):
    # Entity should be there
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    assert eid

    # Open
    await hass.services.async_call("cover", "open_cover", {ATTR_ENTITY_ID: eid}, blocking=True)
    # Close
    await hass.services.async_call("cover", "close_cover", {ATTR_ENTITY_ID: eid}, blocking=True)
    # Stop
    await hass.services.async_call("cover", "stop_cover", {ATTR_ENTITY_ID: eid}, blocking=True)

    # Verify client calls via coordinator
    entry = setup_integration
    coordinator = hass.data[entry.domain][entry.entry_id]
    client = coordinator.client
    client.open_close.assert_any_call(0, "OPEN")
    client.open_close.assert_any_call(0, "CLOSE")
    client.stop.assert_called()


async def test_set_position_maps_to_stop_over(hass, setup_integration):
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    await hass.services.async_call("cover", "set_cover_position", {ATTR_ENTITY_ID: eid, "position": 50}, blocking=True)
    entry = setup_integration
    client = hass.data[entry.domain][entry.entry_id].client
    client.open_close.assert_any_call(0, "STOP_OVER")


async def test_integration_services(hass, setup_integration):
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))

    # set_mode service
    await hass.services.async_call("siegenia", "set_mode", {"entity_id": eid, "mode": "GAP_VENT"}, blocking=True)
    client = hass.data[setup_integration.domain][setup_integration.entry_id].client
    client.open_close.assert_any_call(0, "GAP_VENT")

    # maintenance services
    await hass.services.async_call("siegenia", "reboot_device", {"entity_id": eid}, blocking=True)
    await hass.services.async_call("siegenia", "reset_device", {"entity_id": eid}, blocking=True)
    await hass.services.async_call("siegenia", "renew_cert", {"entity_id": eid}, blocking=True)
    client.reboot_device.assert_called()
    client.reset_device.assert_called()
    client.renew_cert.assert_called()


async def test_prevent_opening_blocks_open(hass, mock_client, config_entry_data):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        options={CONF_PREVENT_OPENING: True},
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cover_eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    select_eid = next(s.entity_id for s in hass.states.async_all("select") if s.entity_id.endswith("_mode"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("cover", "open_cover", {ATTR_ENTITY_ID: cover_eid}, blocking=True)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {ATTR_ENTITY_ID: cover_eid, "position": 50},
            blocking=True,
        )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("select", "select_option", {ATTR_ENTITY_ID: select_eid, "option": "open"}, blocking=True)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("siegenia", "set_mode", {"entity_id": cover_eid, "mode": "OPEN"}, blocking=True)

    # Closing should still work
    await hass.services.async_call("cover", "close_cover", {ATTR_ENTITY_ID: cover_eid}, blocking=True)
    client = hass.data[entry.domain][entry.entry_id].client
    client.open_close.assert_any_call(0, "CLOSE")
