<p align="center">
  <img src="assets/brand/logo.svg" alt="Siegenia Home Assistant" width="520"/>
</p>

# Home Assistant – Siegenia (MHS Family) Integration

This custom integration connects Siegenia window controllers (MHS family) to Home Assistant using the device's local WebSocket API.

- Entity: `cover` with device class `window` (open/close/stop/position slider mapped to discrete modes)
- Sensors: raw window state, open count (persistent)
- Binary sensors: moving, warning active; sensors for warnings count/text and firmware update status
- Online sensor: shows device reachability/active state
- Config Flow: UI-based setup (host, username, password)
- Options: poll interval, heartbeat interval, toggle extra sensors and slider
- Diagnostics: redacted snapshot of config and last device params

The implementation is based on prior Homebridge plugin and Siegenia.NET proof-of-concept.

## Install

- Copy `custom_components/siegenia` into your Home Assistant `config/custom_components` folder.
- Restart Home Assistant.
- Settings → Devices & Services → Add Integration → search for “Siegenia”.

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

## Features

- Open/Close/Stop via `cover` entity
- Slider maps to common modes:
  - 0% → Close
  - 1–19% → Gap vent
  - 20–40% → Close without lock
  - 41–99% → Stop over
  - 100% → Open
- Service `siegenia.set_mode` for discrete actions (`OPEN`, `CLOSE`, `GAP_VENT`, `CLOSE_WO_LOCK`, `STOP_OVER`, `STOP`)
- Number entity: Stopover distance (dm) with live min/max from the device
- Update entity: "Siegenia Firmware" (read-only availability signal from device)
- Service `siegenia.sync_clock` to set device clock to HA's current local time; optional `timezone` parameter (POSIX/TZ string like `CET-1CEST,M3.5.0,M10.5.0/3`).

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

- The controller uses a self-signed TLS certificate; this integration connects with certificate verification disabled for local LAN use.
- Only a single sash (index 0) is exposed currently. Multi-sash support can be added if needed.
- Multi-sash: If your device exposes multiple sashes (states 0/1), entities are created per sash automatically.

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
- CI: GitHub Actions workflow runs tests on Python 3.11 and 3.12 (`.github/workflows/ci.yml`).
- HACS validation: `.github/workflows/validate-hacs.yml` (brands check ignored until brand assets are contributed).
- Hassfest validation: `.github/workflows/hassfest.yml`.

## Branding

- Vector sources are in `assets/brand` and `assets/icons`.
- Generate PNGs for Home Assistant brands submission:
  - `pip install cairosvg`
  - `python tools/gen_brand_icons.py`
  - Outputs in `build/brand/` (`icon.png` 256×256, `logo.png` 512×256)
- To display the icon/logo in the Integrations UI globally, submit a PR to the official `home-assistant/brands` repo adding these files under `brands/siegenia/` with names `icon.png` and `logo.png`.
- Until then, HACS will render the README (with images); devices/entities still work normally.

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
