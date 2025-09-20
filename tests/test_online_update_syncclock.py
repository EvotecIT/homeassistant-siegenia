from homeassistant.const import ATTR_ENTITY_ID


async def test_online_binary_and_update_entity(hass, setup_integration):
    # Entities should be there
    online = hass.states.get("binary_sensor.siegenia_online")
    assert online is not None
    fw = hass.states.get("update.siegenia_firmware")
    assert fw is not None


async def test_sync_clock_service(hass, setup_integration):
    eid = "cover.siegenia_window"
    await hass.services.async_call("siegenia", "sync_clock", {ATTR_ENTITY_ID: eid}, blocking=True)
    entry = setup_integration
    client = hass.data[entry.domain][entry.entry_id].client
    client.set_device_params.assert_called()
