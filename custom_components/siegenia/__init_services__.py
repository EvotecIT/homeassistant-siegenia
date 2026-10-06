from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify as _slug

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SERIAL,
    CONF_USERNAME,
    CONF_WS_PROTOCOL,
    DOMAIN,
    VALID_COMMANDS,
)
from .cover import SiegeniaWindowCover
from .device_registry import async_merge_devices


def _single_entity_id(value: Any) -> str:
    """Accept a field or standard HA target containing exactly one entity."""
    entity_ids = cv.entity_ids(value)
    if len(entity_ids) != 1:
        raise vol.Invalid("Select exactly one entity.")
    return entity_ids[0]


_ENTITY_SCHEMA = vol.Schema({vol.Required("entity_id"): _single_entity_id})
_MODE_SCHEMA = _ENTITY_SCHEMA.extend({vol.Required("mode"): cv.string})
_CONNECTION_SCHEMA = _ENTITY_SCHEMA.extend({
    vol.Optional(CONF_HOST): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional(CONF_PORT): cv.port,
    vol.Optional(CONF_WS_PROTOCOL): vol.In(("ws", "wss")),
    # Preserve the explicit actionable error directing credential changes to UI.
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
})
_CLOCK_SCHEMA = _ENTITY_SCHEMA.extend({vol.Optional("timezone"): cv.string})
_TIMER_SCHEMA = _ENTITY_SCHEMA.extend({vol.Required("duration"): vol.Any(int, str)})
_CLEANUP_SCHEMA = vol.Schema({vol.Optional("entity_id"): _single_entity_id})
_REPAIR_SCHEMA = vol.Schema({
    vol.Optional("rename_entity_ids", default=False): cv.boolean,
    vol.Optional("dry_run", default=True): cv.boolean,
    vol.Optional("only_suffix_none", default=True): cv.boolean,
    vol.Optional("scheme", default="device_entity"): vol.In(("device_entity", "brand_type_place")),
})


def _cover_for_call(hass: HomeAssistant, call: ServiceCall) -> SiegeniaWindowCover:
    """Resolve a loaded Siegenia target without touching unrelated covers."""
    entity_id = call.data.get("entity_id")
    component = hass.data.get("entity_components", {}).get("cover")
    entity = component.get_entity(entity_id) if component and isinstance(entity_id, str) else None
    if not isinstance(entity, SiegeniaWindowCover):
        raise ServiceValidationError(
            "Select a loaded Siegenia cover entity.",
            translation_domain=DOMAIN,
            translation_key="loaded_cover_required",
        )
    return entity


async def async_setup_services(hass: HomeAssistant) -> None:
    async def _handle_set_mode(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        mode: str = str(call.data["mode"]).strip().upper()
        if mode not in VALID_COMMANDS:
            raise ServiceValidationError(
                f"Invalid mode '{mode}' for siegenia.set_mode",
                translation_domain=DOMAIN,
                translation_key="invalid_mode",
                translation_placeholders={"mode": mode},
            )
        # Resolve entity to platform entity
        entity = _cover_for_call(hass, call)
        coordinator = entity.coordinator
        sash = getattr(entity, "_sash", 0)
        await coordinator.async_send_command(
            sash,
            mode,
            source="service:set_mode",
            entity_id=entity_id,
            context=getattr(call, "context", None),
        )
        await coordinator.async_request_refresh()

    async def _handle_set_connection(call: ServiceCall) -> None:
        entity = _cover_for_call(hass, call)
        coordinator = getattr(entity, "coordinator", None)
        entry = getattr(coordinator, "entry", None) if coordinator else None
        if entry is None:
            raise ServiceValidationError(
                "Coordinator missing on entity for siegenia.set_connection",
                translation_domain=DOMAIN,
                translation_key="entry_unavailable",
            )

        if CONF_USERNAME in call.data or CONF_PASSWORD in call.data:
            raise ServiceValidationError(
                "Credentials must be updated via the UI options. "
                "siegenia.set_connection does not accept username/password.",
                translation_domain=DOMAIN,
                translation_key="credentials_in_options",
            )

        new_data = dict(entry.data)
        if CONF_HOST in call.data:
            new_data[CONF_HOST] = call.data[CONF_HOST]
        if call.data.get(CONF_PORT) is not None:
            new_data[CONF_PORT] = call.data[CONF_PORT]
        if call.data.get(CONF_WS_PROTOCOL):
            new_data[CONF_WS_PROTOCOL] = call.data[CONF_WS_PROTOCOL]
        # Preserve cached serial so device registry identifiers stay stable
        if entry.unique_id and CONF_SERIAL not in new_data:
            new_data[CONF_SERIAL] = entry.unique_id

        hass.config_entries.async_update_entry(entry, data=new_data)
        # Reload to apply new connection details cleanly
        await hass.config_entries.async_reload(entry.entry_id)

    async def _wrap_entity(call: ServiceCall, coro_name: str) -> None:
        entity = _cover_for_call(hass, call)
        coordinator = entity.coordinator
        func = getattr(coordinator.client, coro_name)
        await coordinator.async_run_device_action(
            func(),
            action_name=coro_name.replace("_", " "),
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "set_mode", _handle_set_mode, schema=_MODE_SCHEMA)
    hass.services.async_register(DOMAIN, "set_connection", _handle_set_connection, schema=_CONNECTION_SCHEMA)

    async def _cleanup_devices(call: ServiceCall) -> None:
        """Merge duplicate devices for a specific entry and remove empty leftovers.

        Accepts optional entity_id to scope; otherwise uses the first Siegenia entry.
        """
        target_entry_id: str | None = None
        entity_id = call.data.get("entity_id")
        if entity_id is not None:
            ent = er.async_get(hass).async_get(entity_id) if isinstance(entity_id, str) else None
            if ent is None or ent.platform != DOMAIN or not ent.config_entry_id:
                raise ServiceValidationError(
                    "Select a Siegenia entity for cleanup.",
                    translation_domain=DOMAIN,
                    translation_key="cleanup_target_required",
                )
            target_entry_id = ent.config_entry_id
        else:
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                raise ServiceValidationError(
                    "No Siegenia entries found for cleanup",
                    translation_domain=DOMAIN,
                    translation_key="cleanup_no_entries",
                )
            target_entry_id = entries[0].entry_id

        entry = hass.config_entries.async_get_entry(target_entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                "The Siegenia entry is unavailable for cleanup.",
                translation_domain=DOMAIN,
                translation_key="cleanup_entry_unavailable",
            )
        host = entry.data.get(CONF_HOST) if entry else None
        serial = entry.data.get(CONF_SERIAL) if entry else None
        await async_merge_devices(hass, target_entry_id, serial=serial, host=host)

    hass.services.async_register(DOMAIN, "cleanup_devices", _cleanup_devices, schema=_CLEANUP_SCHEMA)

    async def _reboot(call: ServiceCall) -> None:
        await _wrap_entity(call, "reboot_device")

    async def _reset(call: ServiceCall) -> None:
        await _wrap_entity(call, "reset_device")

    async def _renew(call: ServiceCall) -> None:
        await _wrap_entity(call, "renew_cert")

    hass.services.async_register(DOMAIN, "reboot_device", _reboot, schema=_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "reset_device", _reset, schema=_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "renew_cert", _renew, schema=_ENTITY_SCHEMA)

    async def _sync_clock(call: ServiceCall) -> None:
        from homeassistant.util import (
            dt as dt_util,  # local import to avoid startup overhead
        )

        tz: str | None = call.data.get("timezone")
        entity = _cover_for_call(hass, call)
        coordinator = entity.coordinator
        now = dt_util.now()
        payload: dict[str, Any] = {
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
        await coordinator.async_set_device_params(
            payload,
            action_name="synchronize the device clock",
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "sync_clock", _sync_clock, schema=_CLOCK_SCHEMA)

    def _parse_duration(text: object) -> tuple[int, int]:
        """Accept nonnegative whole minutes or hours with a 0-59 minute field."""
        value = str(text).strip()
        try:
            if ":" in value:
                hours_text, minutes_text = value.split(":", 1)
                hours, minutes = int(hours_text), int(minutes_text)
                if hours < 0 or not 0 <= minutes < 60:
                    raise ValueError
                return hours, minutes
            total_minutes = int(value)
            if total_minutes < 0:
                raise ValueError
            return divmod(total_minutes, 60)
        except ValueError as err:
            raise ServiceValidationError(
                "Duration must be nonnegative whole minutes or HH:MM with minutes from 00 to 59.",
                translation_domain=DOMAIN,
                translation_key="invalid_duration",
            ) from err

    async def _timer_start(call: ServiceCall) -> None:
        duration = call.data.get("duration")
        h, m = _parse_duration(duration)
        entity = _cover_for_call(hass, call)
        coordinator = entity.coordinator
        await coordinator.async_set_device_params(
            {"timer": {"duration": {"hour": h, "minute": m}, "enabled": True}},
            action_name="start the timer",
        )
        await coordinator.async_request_refresh()

    async def _timer_stop(call: ServiceCall) -> None:
        entity = _cover_for_call(hass, call)
        coordinator = entity.coordinator
        await coordinator.async_set_device_params(
            {"timer": {"enabled": False}},
            action_name="stop the timer",
        )
        await coordinator.async_request_refresh()

    async def _timer_set_duration(call: ServiceCall) -> None:
        duration = call.data.get("duration")
        h, m = _parse_duration(duration)
        entity = _cover_for_call(hass, call)
        coordinator = entity.coordinator
        await coordinator.async_set_device_params(
            {"timer": {"duration": {"hour": h, "minute": m}}},
            action_name="set the timer duration",
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "timer_start", _timer_start, schema=_TIMER_SCHEMA)
    hass.services.async_register(DOMAIN, "timer_stop", _timer_stop, schema=_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "timer_set_duration", _timer_set_duration, schema=_TIMER_SCHEMA)

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
            persistent_notification.async_create(hass, note, title=title, notification_id="siegenia_repair_names")
        except Exception:
            pass

    hass.services.async_register(DOMAIN, "repair_names", _repair_names, schema=_REPAIR_SCHEMA)
