from homeassistant.const import ATTR_ENTITY_ID


async def test_timer_services(hass, setup_integration):
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    await hass.services.async_call("siegenia", "timer_start", {ATTR_ENTITY_ID: eid, "duration": "10"}, blocking=True)
    await hass.services.async_call("siegenia", "timer_set_duration", {ATTR_ENTITY_ID: eid, "duration": "00:05"}, blocking=True)
    await hass.services.async_call("siegenia", "timer_stop", {ATTR_ENTITY_ID: eid}, blocking=True)
    client = hass.data[setup_integration.domain][setup_integration.entry_id].client
    client.set_device_params.assert_called()
