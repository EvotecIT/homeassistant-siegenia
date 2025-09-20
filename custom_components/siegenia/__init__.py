from __future__ import annotations

from typing import Any
from pathlib import Path
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_HEARTBEAT_INTERVAL,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_USERNAME,
    CONF_HOST,
    PLATFORMS,
    CONF_WARNING_NOTIFICATIONS,
    CONF_WARNING_EVENTS,
    CONF_MOTION_INTERVAL,
    CONF_IDLE_INTERVAL,
    DEFAULT_MOTION_INTERVAL,
    DEFAULT_IDLE_INTERVAL,
)
from .coordinator import SiegeniaDataUpdateCoordinator
from .__init_services__ import async_setup_services
from homeassistant.components.http import HomeAssistantView
from ._brand_assets import ICON_PNG_B64, LOGO_PNG_B64
import base64


def _write_b64(path: Path, b64data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(b64data))


# Compatible type alias for Python 3.11+
SiegeniaConfigEntry = ConfigEntry[SiegeniaDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    from .const import DEFAULT_POLL_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL

    coordinator = SiegeniaDataUpdateCoordinator(
        hass,
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        poll_interval=data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        heartbeat_interval=data.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL),
    )
    # Pass options for warnings routing
    coordinator.warning_notifications = entry.options.get(CONF_WARNING_NOTIFICATIONS, True)
    coordinator.warning_events = entry.options.get(CONF_WARNING_EVENTS, True)
    # Advanced intervals
    motion_s = entry.options.get(CONF_MOTION_INTERVAL, DEFAULT_MOTION_INTERVAL)
    idle_s = entry.options.get(CONF_IDLE_INTERVAL, DEFAULT_IDLE_INTERVAL)
    coordinator._motion_interval = timedelta(seconds=motion_s)  # type: ignore[attr-defined]
    coordinator._idle_interval = timedelta(seconds=idle_s)      # type: ignore[attr-defined]

    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(entry.domain, {})[entry.entry_id] = coordinator

    # Register services once per HA instance using a marker
    marker = f"{DOMAIN}_services_registered"
    if not hass.data.get(marker):
        await async_setup_services(hass)
        hass.data[marker] = True

    # Serve bundled static icons so users can reference them without copying to /local
    static_marker = f"{DOMAIN}_static_paths"
    if not hass.data.get(static_marker):
        try:
            import os
            testing = os.environ.get("PYTEST_CURRENT_TEST") is not None
            icons_path = Path(__file__).parent / "assets" / "icons"
            if icons_path.exists() and not testing:
                hass.http.register_static_path("/siegenia-static/icons", str(icons_path), cache_headers=True)  # type: ignore[attr-defined]
                hass.data[static_marker] = True
            # Optionally expose local brand PNGs if generated (lets Device/Integration tiles show the logo without a Brands PR)
            brand_build = Path(__file__).parent / ".." / ".." / "build" / "brand"
            brand_build = brand_build.resolve()
            brand_build.mkdir(parents=True, exist_ok=True)
            # Write embedded PNGs if missing (done in threadpool to avoid blocking loop)
            try:
                icon_png = brand_build / "icon.png"
                logo_png = brand_build / "logo.png"
                if not icon_png.exists():
                    await hass.async_add_executor_job(_write_b64, icon_png, ICON_PNG_B64)
                if not logo_png.exists():
                    await hass.async_add_executor_job(_write_b64, logo_png, LOGO_PNG_B64)
            except Exception:
                pass

            # Always provide SVG-backed views (crisp branding) and also register static path for PNGs
            assets_brand = Path(__file__).parent / ".." / ".." / "assets" / "brand"
            assets_brand = assets_brand.resolve()

            class _BrandIconView(HomeAssistantView):
                url = "/static/icons/brands/siegenia/icon.png"
                name = "siegenia:brand_icon"
                requires_auth = False

                async def get(self, request):  # type: ignore[override]
                    try:
                        data = (assets_brand / "icon.svg").read_bytes()
                    except Exception:
                        return request.app.make_response(request, 404)  # type: ignore[attr-defined]
                    from aiohttp import web
                    return web.Response(body=data, headers={"Content-Type": "image/svg+xml"})

            class _BrandLogoView(HomeAssistantView):
                url = "/static/icons/brands/siegenia/logo.png"
                name = "siegenia:brand_logo"
                requires_auth = False

                async def get(self, request):  # type: ignore[override]
                    try:
                        data = (assets_brand / "logo.svg").read_bytes()
                    except Exception:
                        return request.app.make_response(request, 404)  # type: ignore[attr-defined]
                    from aiohttp import web
                    return web.Response(body=data, headers={"Content-Type": "image/svg+xml"})

            if not testing:
                hass.http.register_view(_BrandIconView())  # type: ignore[attr-defined]
                hass.http.register_view(_BrandLogoView())  # type: ignore[attr-defined]
                # Also expose static PNG path for HA brand loader
                hass.http.register_static_path("/static/icons/brands/siegenia", str(brand_build), cache_headers=True)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            # If HTTP component is not ready or API changed, skip silently; users can still copy to /local
            pass

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: SiegeniaDataUpdateCoordinator = hass.data[entry.domain].pop(entry.entry_id)
    await coordinator.client.disconnect()
    return unload_ok
