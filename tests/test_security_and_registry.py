import pytest
from unittest.mock import AsyncMock

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
    coordinator = hass.data[entry.domain][entry.entry_id]
    coordinator.auto_discover = True
    coordinator.serial = "af050261"
    coordinator._rediscovery_backoff = 0  # noqa: SLF001
    coordinator._last_rediscovery = None  # noqa: SLF001

    coordinator._rediscover_host = AsyncMock(return_value="192.0.2.99")  # type: ignore[method-assign]
    coordinator._switch_host = AsyncMock()  # type: ignore[method-assign]

    recovered = await coordinator._handle_connection_error(Exception("boom"))  # noqa: BLE001
    assert recovered is True
    coordinator._switch_host.assert_called_once_with("192.0.2.99")


async def test_issue_registry_raise_and_clear(hass, setup_integration):
    entry = setup_integration
    coordinator = hass.data[entry.domain][entry.entry_id]
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
