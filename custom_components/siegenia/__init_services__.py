from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN


async def async_setup_services(hass: HomeAssistant) -> None:
    async def _handle_set_mode(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        mode: str = call.data["mode"]
        # Resolve entity to platform entity
        entity = hass.data["entity_components"]["cover"].get_entity(entity_id)  # type: ignore[index]
        if entity is None:
            return
        coordinator = entity.coordinator  # type: ignore[attr-defined]
        sash = getattr(entity, "_sash", 0)
        if mode == "STOP":
            await coordinator.client.stop(sash)
        else:
            await coordinator.client.open_close(sash, mode)
        await coordinator.async_request_refresh()

    async def _wrap_entity(call: ServiceCall, coro_name: str):
        entity_id: str = call.data["entity_id"]
        entity = hass.data["entity_components"]["cover"].get_entity(entity_id)  # type: ignore[index]
        if entity is None:
            return
        coordinator = entity.coordinator  # type: ignore[attr-defined]
        func = getattr(coordinator.client, coro_name)
        await func()
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "set_mode", _handle_set_mode)

    async def _reboot(call):
        await _wrap_entity(call, "reboot_device")

    async def _reset(call):
        await _wrap_entity(call, "reset_device")

    async def _renew(call):
        await _wrap_entity(call, "renew_cert")

    hass.services.async_register(DOMAIN, "reboot_device", _reboot)
    hass.services.async_register(DOMAIN, "reset_device", _reset)
    hass.services.async_register(DOMAIN, "renew_cert", _renew)

    async def _sync_clock(call: ServiceCall) -> None:
        from homeassistant.util import dt as dt_util  # local import to avoid startup overhead

        entity_id: str = call.data["entity_id"]
        tz: str | None = call.data.get("timezone")
        entity = hass.data["entity_components"]["cover"].get_entity(entity_id)  # type: ignore[index]
        if entity is None:
            return
        coordinator = entity.coordinator  # type: ignore[attr-defined]
        now = dt_util.now()
        payload = {
            "clock": {
                "year": now.year,
                "month": now.month,
                "day": now.day,
                "hour": now.hour,
                "minute": now.minute,
            }
        }
        if tz:
            payload["timezone"] = tz
        await coordinator.client.set_device_params(payload)
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "sync_clock", _sync_clock)
