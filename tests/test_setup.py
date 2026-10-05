"""Integration-wide actions and installed icon delivery."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.siegenia.const import DOMAIN


async def test_setup_serves_installed_icons_without_device(hass, hass_client):
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "set_mode")
    client = await hass_client()
    icons = Path(__file__).parents[1] / "custom_components" / DOMAIN / "icons"
    assert len(list(icons.glob("*.svg"))) == 8
    for icon in icons.glob("*.svg"):
        response = await client.get(f"/siegenia-static/icons/{icon.name}")
        assert response.status == 200
        assert response.content_type == "image/svg+xml"
        assert await response.read() == icon.read_bytes()


@pytest.mark.parametrize("service,data", [
    ("set_mode", {"mode": "OPEN"}),
    ("set_connection", {"host": "192.0.2.5"}),
    ("reboot_device", {}),
    ("reset_device", {}),
    ("renew_cert", {}),
    ("sync_clock", {}),
    ("timer_start", {"duration": "10"}),
    ("timer_stop", {}),
    ("timer_set_duration", {"duration": "10"}),
])
async def test_actions_reject_unloaded_cover(hass, service, data):
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError, match="loaded Siegenia cover"):
        await hass.services.async_call(
            DOMAIN, service, {"entity_id": "cover.missing", **data}, blocking=True,
        )


@pytest.mark.parametrize("target", ["foreign", "missing"])
async def test_cleanup_rejects_explicit_invalid_target(hass, target):
    own_entry = MockConfigEntry(domain=DOMAIN, data={})
    own_entry.add_to_hass(hass)
    foreign_entry = MockConfigEntry(domain="other", data={})
    foreign_entry.add_to_hass(hass)
    foreign = er.async_get(hass).async_get_or_create(
        "cover", "other", "foreign-window", config_entry=foreign_entry,
    )
    # Register actions directly so entries need no network-backed setup.
    from custom_components.siegenia.__init_services__ import async_setup_services

    await async_setup_services(hass)
    with patch(
        "custom_components.siegenia.__init_services__.async_merge_devices",
        new_callable=AsyncMock,
    ) as merge:
        with pytest.raises(ServiceValidationError, match="Siegenia entity"):
            await hass.services.async_call(
                DOMAIN, "cleanup_devices",
                {"entity_id": foreign.entity_id if target == "foreign" else "cover.missing"},
                blocking=True,
            )
        merge.assert_not_awaited()
