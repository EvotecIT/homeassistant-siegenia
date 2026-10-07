from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
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
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"{ISSUE_UNREACHABLE}_{entry.entry_id}",
    )
    assert issue is not None

    await coordinator._clear_issue()  # noqa: SLF001
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"{ISSUE_UNREACHABLE}_{entry.entry_id}",
    )
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


async def test_unreachable_repairs_are_owned_by_each_entry(hass, setup_integration):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.siegenia.coordinator import SiegeniaDataUpdateCoordinator

    first = setup_integration.runtime_data
    second_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.2"})
    second_entry.add_to_hass(hass)
    second = SiegeniaDataUpdateCoordinator(
        hass, entry=second_entry, host="192.0.2.2", port=443,
        username="admin", password="synthetic",
    )
    registry = ir.async_get(hass)
    first_id = f"{ISSUE_UNREACHABLE}_{setup_integration.entry_id}"
    second_id = f"{ISSUE_UNREACHABLE}_{second_entry.entry_id}"
    try:
        await first._raise_issue()
        await second._raise_issue()
        assert registry.async_get_issue(DOMAIN, first_id).data == {
            "entry_id": setup_integration.entry_id,
        }
        assert registry.async_get_issue(DOMAIN, second_id).data == {
            "entry_id": second_entry.entry_id,
        }
        assert registry.async_get_issue(DOMAIN, first_id).is_fixable is False
        await first._clear_issue()
        assert registry.async_get_issue(DOMAIN, first_id) is None
        assert registry.async_get_issue(DOMAIN, second_id) is not None
        # Recovery after reload must not rely on the previous owner's memory.
        second._issue_set = False
        await second._clear_issue()
        assert registry.async_get_issue(DOMAIN, second_id) is None
    finally:
        await second.async_shutdown()


@pytest.mark.parametrize("legacy_owner", ["removed", "retained"])
async def test_removal_clears_only_owned_connection_warnings(hass, legacy_owner):
    from types import SimpleNamespace

    from custom_components.siegenia import async_remove_entry

    registry = ir.async_get(hass)
    for entry_id in ("removed", "retained"):
        ir.async_create_issue(
            hass, DOMAIN, f"{ISSUE_UNREACHABLE}_{entry_id}",
            is_fixable=False, severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_UNREACHABLE, data={"entry_id": entry_id},
        )
    ir.async_create_issue(
        hass, DOMAIN, ISSUE_UNREACHABLE,
        is_fixable=True, severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_UNREACHABLE, data={"entry_id": legacy_owner},
    )
    await async_remove_entry(hass, SimpleNamespace(entry_id="removed"))
    assert registry.async_get_issue(DOMAIN, f"{ISSUE_UNREACHABLE}_removed") is None
    assert registry.async_get_issue(DOMAIN, f"{ISSUE_UNREACHABLE}_retained") is not None
    legacy = registry.async_get_issue(DOMAIN, ISSUE_UNREACHABLE)
    assert (legacy is None) == (legacy_owner == "removed")
