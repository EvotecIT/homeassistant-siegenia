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

    hass.services.async_register(DOMAIN, "set_mode", _handle_set_mode)

