from unittest.mock import AsyncMock

from homeassistant.const import ATTR_ENTITY_ID


async def test_cover_commands(hass, setup_integration):
    # Entity should be there
    eid = "cover.siegenia_window"
    assert hass.states.get(eid) is not None

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
    eid = "cover.siegenia_window"
    await hass.services.async_call("cover", "set_cover_position", {ATTR_ENTITY_ID: eid, "position": 50}, blocking=True)
    entry = setup_integration
    client = hass.data[entry.domain][entry.entry_id].client
    client.open_close.assert_any_call(0, "STOP_OVER")


async def test_integration_services(hass, setup_integration):
    eid = "cover.siegenia_window"

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

