import pytest
from unittest.mock import AsyncMock, Mock

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.siegenia.const import CONF_HOST, DOMAIN, ISSUE_UNREACHABLE
from custom_components.siegenia.device_registry import async_merge_devices


async def test_set_connection_rejects_credentials(hass, setup_integration):
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "siegenia",
            "set_connection",
            {ATTR_ENTITY_ID: eid, "password": "secret"},
            blocking=True,
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "siegenia",
            "set_connection",
            {ATTR_ENTITY_ID: eid, "username": "admin"},
            blocking=True,
        )


async def test_set_connection_updates_host(hass, setup_integration):
    entry = setup_integration
    eid = next(s.entity_id for s in hass.states.async_all("cover") if s.entity_id.endswith("_window"))
    await hass.services.async_call(
        "siegenia",
        "set_connection",
        {ATTR_ENTITY_ID: eid, CONF_HOST: "192.0.2.5"},
        blocking=True,
    )
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.data[CONF_HOST] == "192.0.2.5"


async def test_handle_connection_error_rediscovery(hass, setup_integration):
    entry = setup_integration
    coordinator = entry.runtime_data
    coordinator.auto_discover = True
    coordinator.serial = "00112233"
    coordinator._rediscovery_backoff = 0  # noqa: SLF001
    coordinator._last_rediscovery = None  # noqa: SLF001

    coordinator._rediscover_host = AsyncMock(return_value="192.0.2.99")  # type: ignore[method-assign]
    coordinator._switch_host = AsyncMock()  # type: ignore[method-assign]

    recovered = await coordinator._handle_connection_error(Exception("boom"))  # noqa: BLE001
    assert recovered is True
    coordinator._switch_host.assert_called_once_with("192.0.2.99")


@pytest.mark.parametrize("outcome", ["match", "wrong_serial", "missing_serial", "offline"])
async def test_rediscovery_probe_preserves_identity_and_cleans_up(
    hass, setup_integration, monkeypatch, outcome,
):
    coordinator = setup_integration.runtime_data
    original_info = coordinator.device_info
    original_data = dict(setup_integration.data)
    coordinator.serial = "00112233"
    serial = {"match": "00112233", "wrong_serial": "other"}.get(outcome)
    candidate_info = {"data": {"serialnr": serial, "devicename": "Candidate"}}
    client = Mock()
    client.connect = AsyncMock(side_effect=OSError("offline") if outcome == "offline" else None)
    client.login = AsyncMock()
    client.get_device = AsyncMock(return_value=candidate_info)
    client.disconnect = AsyncMock()
    factory = Mock(return_value=client)
    monkeypatch.setattr("custom_components.siegenia.coordinator.SiegeniaClient", factory)

    result = await coordinator._probe_host("192.0.2.99")

    assert factory.call_args.kwargs["session"] is coordinator.session
    assert coordinator.session is not None and not coordinator.session.closed
    client.disconnect.assert_awaited_once_with()
    assert dict(setup_integration.data) == original_data
    if outcome == "match":
        assert result == "192.0.2.99"
        assert coordinator.device_info == candidate_info
    else:
        assert result is None
        assert coordinator.device_info == original_info
    if outcome == "offline":
        client.login.assert_not_awaited()
        client.get_device.assert_not_awaited()
    else:
        client.login.assert_awaited_once_with(coordinator.username, coordinator.password)


async def test_issue_registry_raise_and_clear(hass, setup_integration):
    entry = setup_integration
    coordinator = entry.runtime_data
    await coordinator._raise_issue()  # noqa: SLF001
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_UNREACHABLE)
    assert issue is not None

    await coordinator._clear_issue()  # noqa: SLF001
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_UNREACHABLE)
    assert issue is None


async def test_async_merge_devices(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.1"}, title="Siegenia Test")
    entry.add_to_hass(hass)

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    dev_primary = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "serial-1")},
        manufacturer="Siegenia",
    )
    dev_secondary = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "serial-2")},
        manufacturer="Siegenia",
    )

    ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="serial-1-state",
        device_id=dev_primary.id,
    )
    secondary_ent = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="serial-2-state",
        device_id=dev_secondary.id,
    )

    await async_merge_devices(hass, entry.entry_id, serial="serial-1", host="192.0.2.1")

    assert ent_reg.async_get(secondary_ent.entity_id).device_id == dev_primary.id
    assert dev_reg.async_get(dev_secondary.id) is None
    primary_dev = dev_reg.async_get(dev_primary.id)
    assert primary_dev is not None
    assert (DOMAIN, "192.0.2.1") in primary_dev.identifiers


async def test_async_merge_devices_no_devices(hass):
    await async_merge_devices(hass, "missing-entry")
