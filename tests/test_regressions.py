from datetime import timedelta
import asyncio

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import entity_registry as er
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)

from custom_components.siegenia.const import (
    CMD_CLOSE_WO_LOCK,
    CONF_HEARTBEAT_INTERVAL,
    CONF_POLL_INTERVAL,
    DOMAIN,
)
from custom_components.siegenia.device_condition import CONDITION_TYPES, async_get_conditions
from custom_components.siegenia.device_trigger import TRIGGER_TYPES, async_get_triggers, async_attach_trigger


async def test_close_wo_lock_mapping(hass, setup_integration):
    entry = setup_integration
    cover_eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    select_eid = next(s.entity_id for s in hass.states.async_all("select") if s.entity_id.endswith("_mode"))

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {ATTR_ENTITY_ID: cover_eid, "position": 30},
        blocking=True,
    )
    client = hass.data[entry.domain][entry.entry_id].client
    client.open_close.assert_any_call(0, CMD_CLOSE_WO_LOCK)

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: select_eid, "option": "close_wo_lock"},
        blocking=True,
    )
    client.open_close.assert_any_call(0, CMD_CLOSE_WO_LOCK)


async def test_unknown_state_not_closed(hass, setup_integration):
    entry = setup_integration
    cover_eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    coordinator = hass.data[entry.domain][entry.entry_id]
    coordinator.async_set_updated_data({"data": {"states": {"0": "MOVING"}}})
    await hass.async_block_till_done()

    entity = hass.data["entity_components"]["cover"].get_entity(cover_eid)  # type: ignore[index]
    assert entity is not None
    assert entity.is_closed is None
    assert entity.current_cover_position is None


async def test_device_automation_suffix_and_state_values(hass, setup_integration):
    ent_reg = er.async_get(hass)
    moving_eid = next(
        s.entity_id for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_moving")
    )
    entry = ent_reg.async_get(moving_eid)
    assert entry is not None
    device_id = entry.device_id
    assert device_id is not None

    triggers = await async_get_triggers(hass, device_id)
    conditions = await async_get_conditions(hass, device_id)

    assert any(t["type"] == "moving_started" and t["entity_id"].endswith("_moving") for t in triggers)
    assert any(t["type"] == "moving_stopped" and t["entity_id"].endswith("_moving") for t in triggers)
    assert any(c["type"] == "is_moving" and c["entity_id"].endswith("_moving") for c in conditions)

    assert TRIGGER_TYPES["closed"]["to"] == "closed"
    assert CONDITION_TYPES["is_closed"]["state"] == "closed"


async def test_options_override_intervals(hass, mock_client, config_entry_data):  # noqa: ARG001
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        options={CONF_POLL_INTERVAL: 12, CONF_HEARTBEAT_INTERVAL: 33},
        title="Siegenia Test",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[entry.domain][entry.entry_id]
    assert coordinator._default_interval == timedelta(seconds=12)  # noqa: SLF001
    assert coordinator.heartbeat_interval == 33


async def test_device_trigger_fires_on_state_change(hass, setup_integration):
    ent_reg = er.async_get(hass)
    state_eid = next(
        s.entity_id for s in hass.states.async_all("sensor") if s.entity_id.endswith("_window_state")
    )
    entry = ent_reg.async_get(state_eid)
    assert entry is not None
    device_id = entry.device_id
    assert device_id is not None

    fired = asyncio.Event()

    async def _action(*_args, **_kwargs):  # noqa: ANN001, ANN002
        fired.set()

    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device_id,
        CONF_ENTITY_ID: state_eid,
        CONF_TYPE: "opened",
    }
    trigger_info = {
        "domain": DOMAIN,
        "name": "test",
        "home_assistant_start": False,
        "variables": {},
        "trigger_data": {"id": "0", "idx": "0", "alias": None},
    }

    unsub = await async_attach_trigger(hass, config, _action, trigger_info)
    hass.states.async_set(state_eid, "open")
    await hass.async_block_till_done()
    await asyncio.wait_for(fired.wait(), timeout=2.0)
    unsub()
