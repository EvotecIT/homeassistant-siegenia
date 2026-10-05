"""Reject invalid action inputs before device or registry mutations."""

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.script import Script

from custom_components.siegenia.const import DOMAIN


@pytest.mark.parametrize("service,data", [
    ("timer_start", {"duration": "-1"}),
    ("timer_start", {"duration": "-01:30"}),
    ("timer_start", {"duration": "00:60"}),
    ("timer_start", {"duration": "invalid"}),
    ("timer_set_duration", {}),
    ("set_connection", {"port": 0}),
    ("set_connection", {"port": 65536}),
    ("set_connection", {"ws_protocol": "ftp"}),
    ("set_mode", {}),
    ("reboot_device", {"entity_id": []}),
    ("reboot_device", {"entity_id": ["cover.first", "cover.second"]}),
])
async def test_invalid_action_input_never_reaches_device(
    hass, setup_integration, hass_ws_client, service, data,
):
    entry = setup_integration
    original_data = dict(entry.data)
    client = entry.runtime_data.client
    client.set_device_params.reset_mock()
    client.open_close.reset_mock()
    client.reboot_device.reset_mock()
    entity_id = next(state.entity_id for state in hass.states.async_all("cover"))
    websocket = await hass_ws_client(hass)
    await websocket.send_json({
        "id": 1, "type": "call_service", "domain": DOMAIN, "service": service,
        "service_data": {"entity_id": entity_id, **data},
    })
    result = await websocket.receive_json()
    assert result["success"] is False
    assert result["error"]["code"] in {
        "invalid_format", "home_assistant_error", "service_validation_error",
    }
    client.set_device_params.assert_not_awaited()
    client.open_close.assert_not_awaited()
    client.reboot_device.assert_not_awaited()
    assert dict(entry.data) == original_data


async def test_false_rename_flag_does_not_rename_registry_entries(hass, setup_integration):
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor", DOMAIN, "validation-sensor", config_entry=setup_integration,
        suggested_object_id="validation_none", original_name="Friendly sensor",
    )
    await hass.services.async_call(
        DOMAIN, "repair_names", {"rename_entity_ids": "false", "dry_run": False},
        blocking=True,
    )
    assert registry.async_get(entity.entity_id) is not None


async def test_timer_normalizes_whole_minutes(hass, setup_integration):
    entity_id = next(state.entity_id for state in hass.states.async_all("cover"))
    client = setup_integration.runtime_data.client
    client.set_device_params.reset_mock()
    await hass.services.async_call(
        DOMAIN, "timer_start", {"entity_id": entity_id, "duration": 90}, blocking=True,
    )
    client.set_device_params.assert_awaited_once_with({
        "timer": {"duration": {"hour": 1, "minute": 30}, "enabled": True},
    })


async def test_documented_automation_target_reaches_selected_cover(hass, setup_integration):
    entity_id = next(state.entity_id for state in hass.states.async_all("cover"))
    client = setup_integration.runtime_data.client
    client.open_close.reset_mock()
    script = Script(hass, [{
        "action": "siegenia.set_mode",
        "target": {"entity_id": entity_id},
        "data": {"mode": "GAP_VENT"},
    }], "Siegenia target validation", DOMAIN)
    await script.async_run()
    client.open_close.assert_awaited_once_with(0, "GAP_VENT")
