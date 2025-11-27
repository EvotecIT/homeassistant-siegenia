<p align="center">
  <img src="assets/brand/logo.svg" alt="Siegenia Home Assistant" width="520"/>
</p>

# Siegenia for Home Assistant (MHS Family)

This custom integration connects Siegenia window controllers (MHS family) to Home Assistant using the device's local WebSocket API.

- Local, fast, and private (LAN only, no cloud)
- Device page with Controls, Sensors, and Diagnostics
- GUI setup, multi‑sash support, and responsive push updates
- Thoughtful extras: mode selector, timers, warnings, and blueprints

## Quick Start

1) Copy `custom_components/siegenia` into your HA `config/custom_components` folder (or add the repo in HACS as a custom integration).
2) Restart Home Assistant.
3) Settings → Devices & Services → Add Integration → “Siegenia”.
4) Enter Host/IP, Username, Password (Port 443, `wss`).
5) Done. A device called “Siegenia” (or your device name) will appear.

### Install via HACS (recommended)

- HACS → Integrations → 3‑dot menu → Custom repositories →
  - Repository: this repo URL
  - Category: Integration
- Add “Siegenia” from HACS, then restart Home Assistant.
- Go to Settings → Devices & Services → Add Integration → “Siegenia”.

## Configuration

- Host/IP: IP of your Siegenia controller
- Username/Password: credentials used in the official app
- Port: default 443
- WS Protocol: `wss`
- Poll Interval: how often device params are polled
- Heartbeat Interval: keep-alive ping interval
- Auto-discover IP changes: enabled by default. If the controller gets a new IP on the same /24 subnet, the integration will scan for it and update the host automatically (Options → Connection).
- Manual reconnect: Use Settings → Devices & Services → Siegenia → Configure → Connection to edit the host/credentials even when the device is offline, or call the `siegenia.set_connection` service.
- Duplicate cleanup: If a legacy “Siegenia Device” remains after IP moves, call `siegenia.cleanup_devices` (Developer Tools → Actions) to merge entities into the main device and remove the empty duplicate.

## Features

- Open/Close/Stop via `cover` entity
- Slider maps to common modes:
  - 0% → Close
  - 1–X% → Gap vent (X configurable in Options)
  - (X+1)–Y% → Close without lock (Y configurable in Options)
  - (Y+1)–99% → Stop over (display % configurable in Options)
  - 100% → Open
- Service `siegenia.set_mode` for discrete actions (`OPEN`, `CLOSE`, `GAP_VENT`, `CLOSE_WO_LOCK`, `STOP_OVER`, `STOP`)
- Number entity: Stopover distance (dm) with live min/max from the device
- Update entity: "Siegenia Firmware" (read-only availability signal from device)
- Service `siegenia.sync_clock` to set device clock to HA's current local time; optional `timezone` parameter (POSIX/TZ string like `CET-1CEST,M3.5.0,M10.5.0/3`).
- Select entity: `select.siegenia_mode` with options (Open/Close/Gap Vent/Close w/o Lock/Stop Over/Stop)
- Timer services: `siegenia.timer_start` (minutes or HH:MM), `siegenia.timer_stop`, `siegenia.timer_set_duration`.
- Device automations: triggers (opened/closed/gap vent/close w/o lock/stop over, moving started/stopped, warning active/cleared) and conditions (is_open/is_closed/is_gap_vent/is_closed_wo_lock/is_stop_over/moving/warning_active).
- Warning routing: options to enable persistent notifications and/or HA events (`siegenia_warning`).
 - Slider threshold options (Options → Integration):
   - Gap Vent max % (default 19)
   - Close w/o lock max % (default 40)
   - Stop Over display % (default 40; use 30/40/90 to match your preference)

### Quick Buttons

- Built-in Button entities (under the device) for: Open, Close, Gap Vent, Close w/o Lock, Stop Over, Stop.
- Optional script blueprint: `blueprints/script/evotecit/siegenia_mode_button.yaml`.
  - Import via Settings → Automations & Scenes → Blueprints → Import Blueprint → paste repo URL, or copy the file into your HA `blueprints/script/...` folder.
  - Create a script from the blueprint, pick your Siegenia cover, and choose the mode. Add the script to your dashboard as a button.

### Online Status + Nightly Clock Sync

- Online chip is included in the Mushroom example YAMLs (uses `binary_sensor.siegenia_online`).
- Nightly clock sync blueprint: `blueprints/automation/evotecit/siegenia_sync_clock_nightly.yaml`.
  - Import in Settings → Automations & Scenes → Blueprints, then create an automation selecting your cover and daily time.

## Notes

- The controller uses a self‑signed TLS certificate; this integration connects with verification disabled for local LAN use.
- Multi‑sash: If your device exposes multiple sashes (states 0/1), entities are created per sash automatically.

## Credits

- Inspiration and protocol reference: Homebridge plugin and Siegenia.NET by the repo author.
- Lovelace Examples

  - Tile (built-in): examples/lovelace/tile-basic.yaml
  - Mushroom (compact): examples/lovelace/mushroom-compact.yaml
  - Mushroom (detailed): examples/lovelace/mushroom-detailed.yaml

  Replace `cover.siegenia_window` and button entity ids with your actual entities (shown under the device). For Mushroom cards, install the “Mushroom” frontend via HACS and reload resources.

## Development

- Run tests locally:
  - `pip install -r requirements_test.txt`
  - `pytest`
- CI: `.github/workflows/ci.yml` (Python 3.11/3.12; Home Assistant installed via pytest-homeassistant-custom-component)
- Validation: `.github/workflows/hassfest.yml`, `.github/workflows/validate-hacs.yml`

## Branding

- Vector sources are in `assets/brand` and `assets/icons`.
- Generate PNGs for the Home Assistant brands repo:
  - `.venv/bin/python tools/gen_brand_icons.py`
  - Outputs: `build/brand/icon.png` (256×256), `logo.png` (512×256), plus `icon@2x.png` and `logo@2x.png`.
- The integration serves any files in `build/brand/` at `/static/icons/brands/siegenia/` so your local instance shows the logo immediately after a restart.
- Full PR checklist and steps: `docs/brands-pr/README.md`.

### Use the custom icons in dashboards

The integration serves its icons directly; no manual copying needed. Reference them as `/siegenia-static/icons/<file>.svg`.

Examples (replace the entity_id with yours):

- Custom button (button-card from HACS):

```yaml
type: custom:button-card
entity: cover.siegenia_window
name: Open
tap_action:
  action: call-service
  service: siegenia.set_mode
  data:
    mode: OPEN
  target:
    entity_id: cover.siegenia_window
show_entity_picture: true
entity_picture: /siegenia-static/icons/window-open.svg
```

- Picture chips row (Mushroom):

```yaml
type: custom:mushroom-chips-card
chips:
  - type: template
    picture: /siegenia-static/icons/stop-over.svg
    content: Stop Over
    tap_action:
      action: call-service
      service: siegenia.set_mode
      data:
        mode: STOP_OVER
      target:
        entity_id: cover.siegenia_window
```

## Reset / Start Over

If you want to wipe configuration and go through setup and Options from scratch:

1) Remove the integration instance
   - Settings → Devices & Services → Integrations → Siegenia → 3‑dot menu → Delete.
   - When prompted, choose “Also delete devices” to remove all entities.
2) Restart Home Assistant (recommended).
3) Add the integration again (Settings → Devices & Services → Add Integration → “Siegenia”).

Optional clean‑ups (rarely needed)
- Developer Tools → Statistics: clear/fix any lingering compiled statistics for removed sensors.
- Browser cache: hard‑refresh (Ctrl/Cmd+Shift+R) to ensure the latest logo/strings load.
- Advanced (only if the UI removal failed): while HA is stopped, remove the old entry from `.storage/core.config_entries` (JSON). Use with care.

### Fix legacy "_none" entity_ids using built‑in tools

Home Assistant can regenerate entity_ids for you based on the current (translated) names:

- Settings → Devices & Services → Entities → filter Integration = Siegenia.
- If any entity shows a customized/blank name, open it and click “Restore name”.
- Select the entities you want to fix → overflow menu → “Recreate entity ID”.

This uses our defaults (`has_entity_name` + `translation_key`) so ids become `cover.<device>_window`, `select.<device>_mode`, etc. If you prefer automation, we also provide a service `siegenia.repair_names` that can clear bad names and (optionally) rename ids. You can choose a scheme:

- `device_entity` (default): `<device>_<entity>` → e.g., `okno_salon_window`.
- `brand_type_place` (optional): `siegenia_<entity>_<device>` → e.g., `siegenia_window_okno_salon`.

Example service data:

```
service: siegenia.repair_names
data:
  rename_entity_ids: true
  dry_run: false
  only_suffix_none: false
  scheme: brand_type_place
```
