from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.util import slugify as _slug

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_WS_PROTOCOL,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SERIAL,
)


async def async_setup_services(hass: HomeAssistant) -> None:
    async def _handle_set_mode(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        mode: str = str(call.data["mode"]).strip().upper()
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
        try:
            coordinator.set_last_cmd(sash, mode)
        except Exception:
            pass
        await coordinator.async_request_refresh()

    async def _handle_set_connection(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        entity = hass.data["entity_components"]["cover"].get_entity(entity_id)  # type: ignore[index]
        if entity is None:
            return
        coordinator = getattr(entity, "coordinator", None)
        entry = getattr(coordinator, "entry", None) if coordinator else None
        if entry is None:
            return

        new_data = dict(entry.data)
        new_data[CONF_HOST] = call.data.get(CONF_HOST, new_data.get(CONF_HOST))
        if call.data.get(CONF_PORT) is not None:
            new_data[CONF_PORT] = call.data[CONF_PORT]
        if call.data.get(CONF_WS_PROTOCOL):
            new_data[CONF_WS_PROTOCOL] = call.data[CONF_WS_PROTOCOL]
        if call.data.get(CONF_USERNAME):
            new_data[CONF_USERNAME] = call.data[CONF_USERNAME]
        if call.data.get(CONF_PASSWORD):
            new_data[CONF_PASSWORD] = call.data[CONF_PASSWORD]
        # Preserve cached serial so device registry identifiers stay stable
        if entry.unique_id and CONF_SERIAL not in new_data:
            new_data[CONF_SERIAL] = entry.unique_id

        hass.config_entries.async_update_entry(entry, data=new_data)
        # Reload to apply new connection details cleanly
        await hass.config_entries.async_reload(entry.entry_id)

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
    hass.services.async_register(DOMAIN, "set_connection", _handle_set_connection)

    async def _cleanup_devices(call: ServiceCall) -> None:
        """Merge duplicate devices and remove empty leftovers.

        Useful when a legacy host-based device remains after IP changes.
        """
        dev_reg = dr.async_get(hass)
        ent_reg = er.async_get(hass)

        # Find all devices for this domain
        devices = [d for d in dev_reg.devices.values() if any(idt[0] == DOMAIN for idt in d.identifiers)]
        if not devices:
            return

        # Choose primary: most identifiers -> tends to be the serial device
        primary = max(devices, key=lambda d: len(d.identifiers))

        for dev in devices:
            if dev.id == primary.id:
                continue
            for ent in list(ent_reg.entities.values()):
                if ent.device_id == dev.id:
                    ent_reg.async_update_entity(ent.entity_id, device_id=primary.id)
            try:
                dev_reg.async_remove_device(dev.id)
            except Exception:
                pass

    hass.services.async_register(DOMAIN, "cleanup_devices", _cleanup_devices)

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

    def _parse_duration(text: str) -> tuple[int, int]:
        # Accept minutes as integer or HH:MM
        text = str(text).strip()
        if ":" in text:
            hh, mm = text.split(":", 1)
            return int(hh), int(mm)
        # minutes-only
        mins = int(text)
        return mins // 60, mins % 60

    async def _timer_start(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        duration = call.data.get("duration")
        h, m = _parse_duration(duration)
        entity = hass.data["entity_components"]["cover"].get_entity(entity_id)  # type: ignore[index]
        if entity is None:
            return
        coordinator = entity.coordinator  # type: ignore[attr-defined]
        await coordinator.client.set_device_params({"timer": {"duration": {"hour": h, "minute": m}, "enabled": True}})
        await coordinator.async_request_refresh()

    async def _timer_stop(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        entity = hass.data["entity_components"]["cover"].get_entity(entity_id)  # type: ignore[index]
        if entity is None:
            return
        coordinator = entity.coordinator  # type: ignore[attr-defined]
        await coordinator.client.set_device_params({"timer": {"enabled": False}})
        await coordinator.async_request_refresh()

    async def _timer_set_duration(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        duration = call.data.get("duration")
        h, m = _parse_duration(duration)
        entity = hass.data["entity_components"]["cover"].get_entity(entity_id)  # type: ignore[index]
        if entity is None:
            return
        coordinator = entity.coordinator  # type: ignore[attr-defined]
        await coordinator.client.set_device_params({"timer": {"duration": {"hour": h, "minute": m}}})
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "timer_start", _timer_start)
    hass.services.async_register(DOMAIN, "timer_stop", _timer_stop)
    hass.services.async_register(DOMAIN, "timer_set_duration", _timer_set_duration)

    async def _repair_names(call: ServiceCall) -> None:
        """Repair entity names and (optionally) entity_ids for this integration.

        Fields:
          - rename_entity_ids: bool (default: False) — also fix entity_id suffixes like *_none
          - dry_run: bool (default: True) — report planned changes without applying
          - only_suffix_none: bool (default: True) — when renaming, limit to ids ending in _none
          - scheme: str (default: "device_entity") — alternative: "brand_type_place"
        """
        rename_ids = bool(call.data.get("rename_entity_ids", False))
        dry_run = bool(call.data.get("dry_run", True))
        only_suffix_none = bool(call.data.get("only_suffix_none", True))
        scheme = str(call.data.get("scheme", "device_entity")).lower()
        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)

        def _child_slug(e: er.RegistryEntry) -> str:
            uid = e.unique_id or ""
            dom = e.domain
            # Cover/select: include sash suffix if present
            sash_suffix = ""
            if "-sash-" in uid:
                try:
                    sash_suffix = f"_sash_{int(uid.split('-sash-')[-1])}"
                except Exception:
                    sash_suffix = ""
            if dom == "cover":
                base = "window"
            elif dom == "select":
                base = "mode"
            elif dom == "binary_sensor":
                if uid.endswith("-online"):
                    base = "online"
                elif uid.endswith("-moving"):
                    base = "moving"
                elif uid.endswith("-warning"):
                    base = "warning_active"
                else:
                    base = _slug(e.original_name or "binary")
            elif dom == "sensor":
                if uid.endswith("-state"):
                    base = "window_state"
                elif uid.endswith("-open-count"):
                    base = "open_count"
                elif uid.endswith("-warnings-count"):
                    base = "warnings_count"
                elif uid.endswith("-warnings-text"):
                    base = "warnings"
                elif uid.endswith("-timer-enabled"):
                    base = "timer_enabled"
                elif uid.endswith("-timer-remaining"):
                    base = "timer_remaining"
                elif uid.endswith("-operation-source"):
                    base = "operation_source"
                elif uid.endswith("-firmware-update"):
                    base = "firmware"
                else:
                    base = _slug(e.original_name or "sensor")
            elif dom == "number":
                base = "stopover_distance" if uid.endswith("-stopover") else _slug(e.original_name or "number")
            elif dom == "update":
                base = "firmware"
            elif dom == "button":
                if "-button-" in uid:
                    base = uid.split("-button-")[-1].replace("-", "_")
                else:
                    base = _slug(e.original_name or "button")
            else:
                base = _slug(e.original_name or dom)
            return f"{base}{sash_suffix}"

        planned: list[str] = []
        changed = 0
        for entry in list(ent_reg.entities.values()):
            if entry.platform != DOMAIN:
                continue
            # Clear bad names (None/none/empty) to allow translation-based default
            bad_name = entry.name in (None, "", "None", "none", "null", "Null")
            if bad_name:
                planned.append(f"clear name for {entry.entity_id}")
                if not dry_run:
                    ent_reg.async_update_entity(entry.entity_id, name=None)
                    changed += 1
            # Optionally rename ids ending with _none or if explicitly requested
            if rename_ids and (not only_suffix_none or entry.entity_id.split(".", 1)[1].endswith("_none")):
                dev = dev_reg.async_get(entry.device_id) if entry.device_id else None
                dev_slug = _slug(dev.name) if dev and dev.name else _slug("siegenia")
                child = _child_slug(entry)
                if scheme == "brand_type_place":
                    suggested_obj_id = f"siegenia_{child}_{dev_slug}"
                else:
                    suggested_obj_id = f"{dev_slug}_{child}"
                new_eid = f"{entry.domain}.{suggested_obj_id}"
                if new_eid != entry.entity_id:
                    planned.append(f"rename {entry.entity_id} -> {new_eid}")
                    if not dry_run:
                        try:
                            ent_reg.async_update_entity(entry.entity_id, new_entity_id=new_eid)
                            changed += 1
                        except Exception:
                            planned.append(f"skip (conflict) {new_eid}")

        note = "\n".join(planned) if planned else "No issues found."
        title = "Siegenia: Name repair (dry-run)" if dry_run else f"Siegenia: Repaired {changed} entries"
        try:
            hass.components.persistent_notification.async_create(note, title=title, notification_id="siegenia_repair_names")
        except Exception:
            pass

    hass.services.async_register(DOMAIN, "repair_names", _repair_names)
