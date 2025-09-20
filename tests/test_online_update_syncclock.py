from homeassistant.const import ATTR_ENTITY_ID


async def test_online_binary_and_update_entity(hass, setup_integration):
    # Entities should be there
    online = next(s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_online"))
    assert online is not None
    fw = next(s for s in hass.states.async_all("update") if s.entity_id.endswith("_firmware"))
    assert fw is not None


async def test_sync_clock_service(hass, setup_integration):
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    await hass.services.async_call("siegenia", "sync_clock", {ATTR_ENTITY_ID: eid}, blocking=True)
    entry = setup_integration
    client = hass.data[entry.domain][entry.entry_id].client
    client.set_device_params.assert_called()
