from homeassistant.const import ATTR_ENTITY_ID


async def test_mode_select_entity(hass, setup_integration):
    eid = next(s.entity_id for s in hass.states.async_all("select") if s.entity_id.endswith("_mode"))
    assert eid

    # Select GAP_VENT
    await hass.services.async_call("select", "select_option", {ATTR_ENTITY_ID: eid, "option": "gap_vent"}, blocking=True)
    client = hass.data[setup_integration.domain][setup_integration.entry_id].client
    client.open_close.assert_any_call(0, "GAP_VENT")

    # Select STOP
    await hass.services.async_call("select", "select_option", {ATTR_ENTITY_ID: eid, "option": "stop"}, blocking=True)
    client.stop.assert_called()
