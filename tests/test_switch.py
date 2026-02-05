from homeassistant.const import ATTR_ENTITY_ID

from custom_components.siegenia.const import CONF_PREVENT_OPENING


async def test_opening_lock_switch_updates_option(hass, setup_integration):
    entry = setup_integration
    switch_eid = next(s.entity_id for s in hass.states.async_all("switch"))

    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: switch_eid}, blocking=True)
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options.get(CONF_PREVENT_OPENING) is True

    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: switch_eid}, blocking=True)
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options.get(CONF_PREVENT_OPENING) is False
