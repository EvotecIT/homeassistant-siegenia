from __future__ import annotations

from datetime import timedelta
import logging
import time
import asyncio
import ipaddress
from typing import Any

from aiohttp import ClientSession, ClientConnectorError, WSServerHandshakeError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Context
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .api import AuthenticationError, SiegeniaClient
from .const import (
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    DEFAULT_WS_PROTOCOL,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_WS_PROTOCOL,
    CONF_AUTO_DISCOVER,
    CONF_SERIAL,
    DEFAULT_AUTO_DISCOVER,
    is_opening_command,
    ISSUE_UNREACHABLE,
    REDISCOVER_COOLDOWN_SECONDS,
    REDISCOVER_BACKOFF_MAX,
    REDISCOVER_MAX_SUBNETS,
    REDISCOVER_MAX_PER_SUBNET,
    REDISCOVER_MAX_HOSTS,
    REDISCOVER_CONCURRENCY,
    PROBE_TIMEOUT,
)


class SiegeniaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
        host: str,
        port: int,
        username: str,
        password: str,
        ws_protocol: str = DEFAULT_WS_PROTOCOL,
        auto_discover: bool = DEFAULT_AUTO_DISCOVER,
        extended_discovery: bool = False,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL,
        session: ClientSession | None = None,
    ) -> None:
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=f"Siegenia {host}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.entry = entry
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ws_protocol = ws_protocol or DEFAULT_WS_PROTOCOL
        self.auto_discover = bool(auto_discover)
        # Keep a stable serial/identifier across IP changes
        self.serial: str | None = entry.data.get(CONF_SERIAL) or entry.unique_id
        self.heartbeat_interval = heartbeat_interval
        self.client = SiegeniaClient(host, port=port, ws_protocol=self.ws_protocol, session=session, logger=self.logger.debug)
        self.device_info: dict[str, Any] | None = None
        self._issue_lock = asyncio.Lock()
        self.extended_discovery = bool(extended_discovery)
        # Push/poll strategy
        self._default_interval = timedelta(seconds=poll_interval)
        self._push_interval = timedelta(seconds=max(poll_interval * 6, 30))
        self._idle_interval = timedelta(seconds=max(poll_interval * 10, 60))
        self._motion_interval = timedelta(seconds=max(1, min(2, poll_interval)))
        self._push_idle_timeout = 60
        self._last_push_monotonic: float | None = None
        self._revert_handle = None
        # Warnings tracking
        self._last_warnings: str | None = None
        # Optional logging toggles
        self.debug_logging: bool = False
        self.informational_logging: bool = False
        self._last_logged_states: dict[str, str | None] = {}
        # Options toggles (set from setup_entry)
        self.warning_notifications: bool = True
        self.warning_events: bool = True
        self._motion_revert_handle = None
        self.prevent_opening: bool = False
        # Last command per sash (shared across entities for better UX during motion)
        self._last_cmd_by_sash: dict[int, str | None] = {}
        self._last_cmd_ts_by_sash: dict[int, float] = {}
        self._last_stable_state_by_sash: dict[int, str | None] = {}
        self._manual_active_by_sash: dict[int, bool] = {}
        self._last_rediscovery: float | None = None
        self._rediscovery_backoff = REDISCOVER_COOLDOWN_SECONDS
        self._issue_set = False
        # Push updates from device (no id) – update coordinator data immediately
        def _on_push(msg: dict[str, Any]) -> None:
            cmd = msg.get("command")
            if cmd in {"getDeviceParams", "deviceParams"} and "data" in msg:
                # Update data and switch to push-optimized interval immediately
                # (tests call this callback directly on the event loop thread).
                try:
                    self._handle_push_update(msg)
                except Exception:
                    # Fallback to scheduling if we're on a different thread
                    self.hass.loop.call_soon_threadsafe(self._handle_push_update, msg)

        self._push_callback = _on_push
        try:
            self.client.set_push_callback(self._push_callback)
        except Exception:
            pass
        self._issue_set = False

    # Shared helpers for entities
    def set_last_cmd(self, sash: int, cmd: str | None) -> None:
        s = int(sash)
        self._last_cmd_by_sash[s] = cmd
        self._last_cmd_ts_by_sash[s] = time.monotonic()

    def get_last_cmd(self, sash: int) -> str | None:
        return self._last_cmd_by_sash.get(int(sash))

    def is_recent_cmd(self, sash: int, within: float = 5.0) -> bool:
        ts = self._last_cmd_ts_by_sash.get(int(sash))
        return ts is not None and (time.monotonic() - ts) <= within

    def get_last_stable_state(self, sash: int) -> str | None:
        return self._last_stable_state_by_sash.get(int(sash))

    def device_identifier(self) -> str:
        """Return the stable identifier (serial preferred) for entities."""
        return self.serial or self.entry.unique_id or self.host

    def device_serial(self) -> str:
        """Return the preferred serial/identifier for unique_id prefixes.

        We prefer the device-reported serial when available to avoid host-based
        unique_ids, even before the entry serial is persisted.
        """
        info_serial = ((self.device_info or {}).get("data") or {}).get("serialnr")
        return self.serial or info_serial or self.entry.unique_id or self.host

    def _emit_command_event(
        self,
        *,
        command: str,
        sash: int,
        source: str,
        blocked: bool,
        entity_id: str | None,
        context: Context | None,
        user_name: str | None,
        origin: dict[str, Any] | None,
    ) -> None:
        try:
            serial = ((self.device_info or {}).get("data", {}) or {}).get("serialnr") or self.serial
            self.hass.bus.async_fire(
                "siegenia_command",
                {
                    "host": self.host,
                    "serial": serial,
                    "sash": sash,
                    "command": command,
                    "source": source,
                    "entity_id": entity_id,
                    "blocked": blocked,
                    "context_id": getattr(context, "id", None),
                    "user_id": getattr(context, "user_id", None),
                    "parent_id": getattr(context, "parent_id", None),
                    "user_name": user_name,
                    "origin": origin,
                },
            )
        except Exception:
            pass

    async def async_send_command(
        self,
        sash: int,
        command: str,
        *,
        source: str,
        entity_id: str | None = None,
        context: Context | None = None,
    ) -> None:
        cmd = str(command).strip().upper()
        user_name = self._context_user_name(context)
        origin = self._context_origin(context)
        if self.prevent_opening and is_opening_command(cmd):
            self.logger.warning(
                "Blocked opening command %s (sash %s) from %s due to prevent_opening option",
                cmd,
                sash,
                source,
            )
            self._emit_command_event(
                command=cmd,
                sash=sash,
                source=source,
                blocked=True,
                entity_id=entity_id,
                context=context,
                user_name=user_name,
                origin=origin,
            )
            self._log_command(cmd, sash, source, entity_id, blocked=True, user_name=user_name)
            raise HomeAssistantError("Opening commands are disabled in Siegenia options.")
        if cmd == "STOP":
            await self.client.stop(sash)
        else:
            await self.client.open_close(sash, cmd)
        self.set_last_cmd(sash, cmd)
        self._emit_command_event(
            command=cmd,
            sash=sash,
            source=source,
            blocked=False,
            entity_id=entity_id,
            context=context,
            user_name=user_name,
            origin=origin,
        )
        self._log_command(cmd, sash, source, entity_id, blocked=False, user_name=user_name)

    def _context_user_name(self, context: Context | None) -> str | None:
        if context is None or not context.user_id:
            return None
        try:
            user = self.hass.auth.async_get_user(context.user_id)
            return getattr(user, "name", None) if user else None
        except Exception:
            return None

    def _context_origin(self, context: Context | None) -> dict[str, Any] | None:
        if context is None or context.origin_event is None:
            return None
        event = context.origin_event
        data = event.data or {}
        origin: dict[str, Any] = {"event_type": event.event_type}
        if "domain" in data:
            origin["domain"] = data.get("domain")
        if "service" in data:
            origin["service"] = data.get("service")
        if "entity_id" in data:
            origin["entity_id"] = data.get("entity_id")
        if "platform" in data:
            origin["platform"] = data.get("platform")
        if "trigger" in data and isinstance(data.get("trigger"), dict):
            trig = data["trigger"]
            origin["trigger"] = {
                k: trig.get(k)
                for k in ("platform", "entity_id", "from_state", "to_state", "at", "event_type")
                if k in trig
            }
        return origin

    def _log_command(
        self,
        cmd: str,
        sash: int,
        source: str,
        entity_id: str | None,
        blocked: bool,
        user_name: str | None,
    ) -> None:
        if not self.informational_logging:
            return
        serial = ((self.device_info or {}).get("data", {}) or {}).get("serialnr") or self.serial or self.host
        status = "BLOCKED" if blocked else "sent"
        msg = f"Command {status}: {cmd} (sash {sash}) via {source}"
        if entity_id:
            msg = f"{msg} ({entity_id})"
        if user_name:
            msg = f"{msg} user={user_name}"
        self.logger.info("Siegenia %s: %s", serial, msg)
        try:
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "logbook",
                    "log",
                    {"name": f"Siegenia {serial}", "message": msg, "domain": "siegenia"},
                    blocking=False,
                )
            )
        except Exception:
            pass

    async def _ensure_connected(self) -> None:
        if self.client.connected:
            return
        try:
            await self.client.connect()
            await self.client.login(self.username, self.password)
            await self.client.start_heartbeat(self.heartbeat_interval)
        except (ClientConnectorError, TimeoutError, asyncio.TimeoutError, WSServerHandshakeError, OSError, AuthenticationError) as exc:
            raise UpdateFailed(exc) from exc
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Unexpected ensure_connected failure: %s", exc)
            raise UpdateFailed(exc) from exc

    async def _handle_connection_error(self, err: Exception) -> bool:
        """Try to recover from connection errors by rediscovering the host.

        Returns True if a new host was found and set, signalling the caller to retry
        the data update immediately.
        """
        # Auth errors are handled elsewhere
        if not self.auto_discover:
            return False
        # Require a known serial/unique_id to avoid hijacking a different device
        if not self.serial:
            return False
        # Avoid tight rediscovery loops with backoff
        now = time.monotonic()
        if self._last_rediscovery and (now - self._last_rediscovery) < self._rediscovery_backoff:
            return False

        self._last_rediscovery = now
        try:
            new_host = await self._rediscover_host()
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Rediscovery failed: %s", exc)
            self._rediscovery_backoff = min(self._rediscovery_backoff * 2, REDISCOVER_BACKOFF_MAX)
            return False

        if not new_host or new_host == self.host:
            self._rediscovery_backoff = min(self._rediscovery_backoff * 2, REDISCOVER_BACKOFF_MAX)
            return False

        await self._switch_host(new_host)
        self._rediscovery_backoff = REDISCOVER_COOLDOWN_SECONDS
        return True

    def _update_serial(self, serial: str | None) -> None:
        if not serial:
            return
        if serial == self.serial:
            return
        self.serial = serial
        data = dict(self.entry.data)
        data[CONF_SERIAL] = serial
        self.hass.config_entries.async_update_entry(self.entry, data=data)

    async def _raise_issue(self) -> None:
        async with self._issue_lock:
            if self._issue_set:
                return
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_UNREACHABLE,
                is_fixable=True,
                breaks_in_ha_version=None,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_UNREACHABLE,
                translation_placeholders={"host": self.host},
                data={"entry_id": self.entry.entry_id},
            )
            self._issue_set = True

    async def _clear_issue(self) -> None:
        async with self._issue_lock:
            if not self._issue_set:
                return
            try:
                ir.async_delete_issue(self.hass, DOMAIN, ISSUE_UNREACHABLE)
            except Exception:
                pass
            self._issue_set = False

    async def _rediscover_host(self) -> str | None:
        """Scan the previous subnet for the device.

        We limit to the /24 that contained the last known host and stop at the
        first match that successfully authenticates (and, if known, matches the
        stored serial number).
        """
        try:
            current_ip = ipaddress.ip_address(self.host)
        except ValueError:
            return None

        if current_ip.version != 4:
            return None

        # Build subnets to probe: previous /24 plus optional common home nets if extended
        nets: list[ipaddress.IPv4Network] = [ipaddress.ip_network(f"{self.host}/24", strict=False)]
        if self.extended_discovery:
            common = ["192.168.0.0/24", "192.168.1.0/24", "10.0.0.0/24", "172.16.0.0/24"]
            for n in common[: REDISCOVER_MAX_SUBNETS - 1]:
                net = ipaddress.ip_network(n)
                if net not in nets:
                    nets.append(net)

        candidates: list[ipaddress.IPv4Address] = []
        for net in nets:
            hosts = list(net.hosts())
            if net.supernet_of(ipaddress.ip_network(f"{self.host}/32")):
                center = int(current_ip)
                hosts = sorted(hosts, key=lambda ip: abs(int(ip) - center))
            candidates.extend(hosts[:REDISCOVER_MAX_PER_SUBNET])

        seen = set()
        deduped: list[ipaddress.IPv4Address] = []
        for ip in candidates:
            if ip not in seen:
                seen.add(ip)
                deduped.append(ip)
        candidates = deduped[:REDISCOVER_MAX_HOSTS]

        semaphore = asyncio.Semaphore(REDISCOVER_CONCURRENCY)

        async def _runner(ip_obj: ipaddress.IPv4Address):
            async with semaphore:
                return await self._probe_host(str(ip_obj))

        tasks = [asyncio.create_task(_runner(ip)) for ip in candidates]
        found = None
        try:
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug("Probe task failed: %s", exc)
                    continue
                if result:
                    found = result
                    break
        finally:
            # Cancel remaining tasks
            for t in tasks:
                if not t.done():
                    t.cancel()
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception:
                pass
        return found

    async def _probe_host(self, host: str) -> str | None:
        if not self.serial:
            return None
        client = SiegeniaClient(
            host,
            port=self.port,
            ws_protocol=self.ws_protocol,
            response_timeout=PROBE_TIMEOUT,
            logger=self.logger.debug,
        )
        try:
            await client.connect()
            await client.login(self.username, self.password)
            info = await client.get_device()
            serial = ((info or {}).get("data") or {}).get("serialnr")
            if not serial or (self.serial and serial != self.serial):
                return None
            # Update cached info if this looks like our device
            self.device_info = info or self.device_info
            self._update_serial(serial)
            return host
        except AuthenticationError:
            return None
        except (ClientConnectorError, TimeoutError, asyncio.TimeoutError, WSServerHandshakeError, OSError):
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Probe %s failed: %s", host, exc)
            return None
        finally:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=2.0)
            except Exception as exc:  # noqa: BLE001
                self.logger.debug("Probe cleanup failed for %s: %s", host, exc)

    async def _switch_host(self, new_host: str) -> None:
        self.logger.info("Detected Siegenia IP change: %s -> %s", self.host, new_host)
        try:
            await self.client.disconnect()
        except Exception:
            pass
        self.host = new_host
        self.name = f"Siegenia {new_host}"
        # Replace client and preserve push callback
        self.client = SiegeniaClient(
            new_host,
            port=self.port,
            ws_protocol=self.ws_protocol,
            logger=self.logger.debug,
        )
        if self._push_callback:
            try:
                self.client.set_push_callback(self._push_callback)
            except Exception:
                self.logger.debug("Failed to rebind push callback after host switch")
        # Ensure we still have a serial cached
        if self.serial:
            self._update_serial(self.serial)
        # Persist host change on the config entry
        data = dict(self.entry.data)
        data[CONF_HOST] = new_host
        data.setdefault(CONF_PORT, self.port)
        data.setdefault(CONF_USERNAME, self.username)
        data.setdefault(CONF_PASSWORD, self.password)
        data.setdefault(CONF_WS_PROTOCOL, self.ws_protocol)
        data.setdefault(CONF_AUTO_DISCOVER, self.auto_discover)
        if self.serial:
            data.setdefault(CONF_SERIAL, self.serial)
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        await self._clear_issue()

    async def async_setup(self) -> None:
        await self.client.connect()
        await self.client.login(self.username, self.password)
        await self.client.start_heartbeat(self.heartbeat_interval)
        # Prime device info once
        try:
            self.device_info = await self.client.get_device()
            data = (self.device_info or {}).get("data") or {}
            self._update_serial(data.get("serialnr"))
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Failed to get device info during setup: %s", exc)

    async def _async_update_data(self) -> dict[str, Any]:
        attempts = 0
        while attempts < 2:
            try:
                await self._ensure_connected()
                params = await self.client.get_device_params()
                self._adjust_interval(params)
                self._maybe_log_states(params, source="poll")
                # Check warnings on polled data too
                self._handle_warnings(params)
                await self._clear_issue()
                # Track last stable states per sash for UX when MOVING without a recent command
                try:
                    states = ((params or {}).get("data") or {}).get("states") or {}
                    for k, v in states.items():
                        if v and v != "MOVING":
                            self._last_stable_state_by_sash[int(k)] = v
                except Exception:
                    pass
                return params
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed from err
            except Exception as err:  # noqa: BLE001
                recovered = await self._handle_connection_error(err)
                if recovered:
                    attempts += 1
                    continue
                await self._raise_issue()
                raise UpdateFailed(err) from err
        # Should not reach here
        raise UpdateFailed("Failed after retry")

    def _handle_push_update(self, msg: dict[str, Any]) -> None:
        # Mark push as active; slow down poller while push is flowing
        self._last_push_monotonic = time.monotonic()
        # Prefer motion interval if moving; else push interval
        states_map = (msg.get("data") or {}).get("states", {})
        self._maybe_log_states(msg, source="push")
        moving = any(v == "MOVING" for v in states_map.values())
        if moving:
            self.update_interval = self._motion_interval
        else:
            self.update_interval = self._push_interval

        # schedule revert after idle timeout
        if self._revert_handle is not None:
            self._revert_handle()  # cancel
            self._revert_handle = None

        def _revert(_now):  # noqa: ANN001
            if self._last_push_monotonic and (time.monotonic() - self._last_push_monotonic) >= self._push_idle_timeout:
                self.update_interval = self._default_interval
                self._revert_handle = None
            else:
                self._revert_handle = async_call_later(self.hass, self._push_idle_timeout, _revert)

        self._revert_handle = async_call_later(self.hass, self._push_idle_timeout, _revert)
        # Merge push payload into last known params to avoid losing keys (e.g., timer)
        merged = self.data or {}
        try:
            if not merged:
                merged = msg
            else:
                md = dict(merged)
                nd = dict(msg)
                mdata = dict(md.get("data") or {})
                ndata = dict(nd.get("data") or {})
                mdata.update(ndata)
                md["data"] = mdata
                merged = md
        except Exception:
            merged = msg
        self.async_set_updated_data(merged)
        # Track last stable states
        try:
            for k, v in states_map.items():
                if v and v != "MOVING":
                    self._last_stable_state_by_sash[int(k)] = v
        except Exception:
            pass
        # Update serial if delivered in push payload (rare)
        try:
            data = (msg or {}).get("data") or {}
            self._update_serial(data.get("serialnr"))
        except Exception:
            pass
        # Detect manual operation edges and emit log/event once
        try:
            for k, v in states_map.items():
                sash = int(k)
                moving = v == "MOVING"
                recent = self.is_recent_cmd(sash, within=5.0)
                manual = bool(moving and not recent)
                prev = self._manual_active_by_sash.get(sash, False)
                if manual and not prev:
                    # Edge: manual started
                    self._manual_active_by_sash[sash] = True
                    self._log_manual_operation(sash)
                elif not manual and prev:
                    self._manual_active_by_sash[sash] = False
        except Exception:
            pass
        # Handle warnings immediately; in tests the listener is set up before push
        # and a subsequent sleep(0) will process this event.
        self._handle_warnings(msg)

    def _log_manual_operation(self, sash: int) -> None:
        try:
            serial = ((self.device_info or {}).get("data", {}) or {}).get("serialnr") or self.host
            name = f"Siegenia {serial}"
            msg = f"Manual operation detected (sash {sash})"
            # Best-effort logbook entry
            try:
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "logbook",
                        "log",
                        {"name": name, "message": msg, "domain": "siegenia"},
                        blocking=False,
                    )
                )
            except Exception:
                pass
            # Also fire a dedicated event for automations
            self.hass.bus.async_fire(
                "siegenia_operation",
                {
                    "host": self.host,
                    "serial": serial,
                    "sash": sash,
                    "manual": True,
                    "last_command": self.get_last_cmd(sash),
                },
            )
        except Exception:
            pass

    def _adjust_interval(self, payload: dict[str, Any]) -> None:
        data = (payload or {}).get("data") or {}
        states = (data.get("states") or {}).values()
        if any(s == "MOVING" for s in states):
            # Speed up while moving
            self.update_interval = self._motion_interval
            # schedule a revert after short delay if motion stops
            if self._motion_revert_handle is not None:
                self._motion_revert_handle()
                self._motion_revert_handle = None

            def _revert(_now):  # noqa: ANN001
                # If not moving anymore, go to idle interval
                self.update_interval = self._idle_interval
                self._motion_revert_handle = None

            from homeassistant.helpers.event import async_call_later as _later

            self._motion_revert_handle = _later(self.hass, 10, _revert)
        else:
            # Idle: lengthen
            self.update_interval = self._idle_interval

    def _maybe_log_states(self, payload: dict[str, Any], *, source: str) -> None:
        if not (self.debug_logging or self.informational_logging):
            return
        data = (payload or {}).get("data") or {}
        states = data.get("states") or {}
        if not states:
            return
        if self.debug_logging:
            self.logger.info("Siegenia %s states: %s", source, states)
            return
        changes: list[str] = []
        for k, v in states.items():
            key = str(k)
            last = self._last_logged_states.get(key)
            if v != last:
                changes.append(f"sash {key}: {last} -> {v}")
                self._last_logged_states[key] = v
        if changes:
            self.logger.info("Siegenia state change (%s): %s", source, ", ".join(changes))

    def _handle_warnings(self, payload: dict[str, Any]) -> None:
        data = (payload or {}).get("data") or {}
        if "warnings" not in data:
            return
        warnings = data.get("warnings") or []
        key = ";".join(map(lambda w: w if isinstance(w, str) else str(w), warnings)) if warnings else ""
        if key == (self._last_warnings or ""):
            return
        serial = ((self.device_info or {}).get("data", {}) or {}).get("serialnr")
        notif_id = f"siegenia_warning_{serial or self.host}"
        if warnings:
            if self.warning_notifications:
                try:
                    from homeassistant.components.persistent_notification import (
                        async_create as pn_create,
                    )

                    pn_create(
                        self.hass,
                        key or "Warning reported",
                        title="Siegenia Warning",
                        notification_id=notif_id,
                    )
                except Exception:
                    pass
            if self.warning_events:
                self.hass.bus.async_fire(
                    "siegenia_warning",
                    {"host": self.host, "serial": serial, "warnings": warnings, "cleared": False},
                )
        else:
            if self.warning_notifications:
                try:
                    from homeassistant.components.persistent_notification import (
                        async_dismiss as pn_dismiss,
                    )

                    pn_dismiss(self.hass, notif_id)
                except Exception:
                    pass
            if self.warning_events:
                self.hass.bus.async_fire(
                    "siegenia_warning",
                    {"host": self.host, "serial": serial, "warnings": [], "cleared": True},
                )
        self._last_warnings = key
