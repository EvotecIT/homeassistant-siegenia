from __future__ import annotations

from datetime import timedelta
import logging
import time
import asyncio
import ipaddress
from typing import Any

from aiohttp import ClientSession, ClientConnectorError, WSServerHandshakeError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir

from .api import AuthenticationError, SiegeniaClient
from .const import (
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_WS_PROTOCOL,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_WS_PROTOCOL,
    CONF_AUTO_DISCOVER,
    CONF_SERIAL,
    DEFAULT_AUTO_DISCOVER,
    ISSUE_UNREACHABLE,
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
        # Options toggles (set from setup_entry)
        self.warning_notifications: bool = True
        self.warning_events: bool = True
        self._motion_revert_handle = None
        # Last command per sash (shared across entities for better UX during motion)
        self._last_cmd_by_sash: dict[int, str | None] = {}
        self._last_cmd_ts_by_sash: dict[int, float] = {}
        self._last_stable_state_by_sash: dict[int, str | None] = {}
        self._manual_active_by_sash: dict[int, bool] = {}
        self._last_rediscovery: float | None = None
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

    async def _ensure_connected(self) -> None:
        if self.client.connected:
            return
        await self.client.connect()
        await self.client.login(self.username, self.password)
        await self.client.start_heartbeat(self.heartbeat_interval)

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
        # Avoid tight rediscovery loops
        now = time.monotonic()
        if self._last_rediscovery and (now - self._last_rediscovery) < 900:
            return False

        self._last_rediscovery = now
        try:
            new_host = await self._rediscover_host()
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Rediscovery failed: %s", exc)
            return False

        if not new_host or new_host == self.host:
            return False

        await self._switch_host(new_host)
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

    def _raise_issue(self) -> None:
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

    def _clear_issue(self) -> None:
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

        # Build a small set of subnets to probe: previous /24 plus common home nets
        nets: list[ipaddress.IPv4Network] = [ipaddress.ip_network(f"{self.host}/24", strict=False)]
        common = ["192.168.0.0/24", "192.168.1.0/24", "10.0.0.0/24", "172.16.0.0/24"]
        for n in common:
            net = ipaddress.ip_network(n)
            if net not in nets:
                nets.append(net)

        candidates: list[ipaddress.IPv4Address] = []
        for net in nets:
            hosts = list(net.hosts())
            if net.supernet_of(ipaddress.ip_network(f"{self.host}/32")):
                # prioritize addresses closest to old IP
                center = int(current_ip)
                hosts = sorted(hosts, key=lambda ip: abs(int(ip) - center))
            # limit per subnet to keep scan bounded
            candidates.extend(hosts[:64])

        # Deduplicate while preserving order
        seen = set()
        deduped: list[ipaddress.IPv4Address] = []
        for ip in candidates:
            if ip not in seen:
                seen.add(ip)
                deduped.append(ip)
        candidates = deduped[:192]

        semaphore = asyncio.Semaphore(8)

        async def _runner(ip_obj: ipaddress.IPv4Address):
            async with semaphore:
                return await self._probe_host(str(ip_obj))

        tasks = [asyncio.create_task(_runner(ip)) for ip in candidates]
        for task in asyncio.as_completed(tasks):
            host = await task
            if host:
                # Cancel any remaining probes
                for t in tasks:
                    if not t.done():
                        t.cancel()
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception:
                    pass
                return host
        return None

    async def _probe_host(self, host: str) -> str | None:
        client = SiegeniaClient(
            host,
            port=self.port,
            ws_protocol=self.ws_protocol,
            response_timeout=3.0,
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
            # Wrong device or creds; skip
            return None
        except (ClientConnectorError, TimeoutError, asyncio.TimeoutError, WSServerHandshakeError, OSError):
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Probe %s failed: %s", host, exc)
            return None
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

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
                pass
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
        self._clear_issue()

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
        try:
            await self._ensure_connected()
            params = await self.client.get_device_params()
            self._adjust_interval(params)
            # Check warnings on polled data too
            self._handle_warnings(params)
            self._clear_issue()
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
            # Trigger reauth flow in HA
            raise ConfigEntryAuthFailed from err
        except Exception as err:  # noqa: BLE001
            recovered = await self._handle_connection_error(err)
            if recovered:
                # Try once more immediately after recovery
                return await self._async_update_data()
            self._raise_issue()
            raise UpdateFailed(err) from err

    def _handle_push_update(self, msg: dict[str, Any]) -> None:
        # Mark push as active; slow down poller while push is flowing
        self._last_push_monotonic = time.monotonic()
        # Prefer motion interval if moving; else push interval
        states_map = (msg.get("data") or {}).get("states", {})
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

    def _handle_warnings(self, payload: dict[str, Any]) -> None:
        data = (payload or {}).get("data") or {}
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
