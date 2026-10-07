from homeassistant.const import ATTR_ENTITY_ID
from unittest.mock import call
import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.siegenia.api import AuthenticationError, SiegeniaError


async def test_timer_services(hass, setup_integration):
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    client = setup_integration.runtime_data.client
    client.set_device_params.reset_mock()
    await hass.services.async_call("siegenia", "timer_start", {ATTR_ENTITY_ID: eid, "duration": "10"}, blocking=True)
    await hass.services.async_call("siegenia", "timer_set_duration", {ATTR_ENTITY_ID: eid, "duration": "00:05"}, blocking=True)
    await hass.services.async_call("siegenia", "timer_stop", {ATTR_ENTITY_ID: eid}, blocking=True)
    assert client.set_device_params.await_args_list == [
        call({"timer": {"duration": {"hour": 0, "minute": 10}, "enabled": True}}),
        call({"timer": {"duration": {"hour": 0, "minute": 5}}}),
        call({"timer": {"enabled": False}}),
    ]


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [(AuthenticationError("expired"), "authentication_failed"),
     (SiegeniaError("offline"), "device_action_failed")],
)
async def test_timer_failure_returns_translated_action_error(hass, setup_integration, error, translation_key):
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    client = setup_integration.runtime_data.client
    client.set_device_params.side_effect = error
    client.get_device_params.reset_mock()
    with pytest.raises(HomeAssistantError) as caught:
        await hass.services.async_call(
            "siegenia", "timer_start", {ATTR_ENTITY_ID: eid, "duration": "10"}, blocking=True,
        )
    assert caught.value.translation_domain == "siegenia"
    assert caught.value.translation_key == translation_key
    client.get_device_params.assert_not_awaited()
