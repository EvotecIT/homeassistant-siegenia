# Home Assistant – Siegenia (MHS Family) Integration

This custom integration connects Siegenia window controllers (MHS family) to Home Assistant using the device's local WebSocket API.

- Entity: `cover` with device class `window` (open/close/stop/position slider mapped to discrete modes)
- Sensors: raw window state, open count (persistent)
- Binary sensor: moving
- Config Flow: UI-based setup (host, username, password)
- Options: poll interval, heartbeat interval, toggle extra sensors and slider
- Diagnostics: redacted snapshot of config and last device params

The implementation is based on the author's prior Homebridge plugin and Siegenia.NET proof-of-concept.

## Install

- Copy `custom_components/siegenia` into your Home Assistant `config/custom_components` folder.
- Restart Home Assistant.
- Settings → Devices & Services → Add Integration → search for “Siegenia”.

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

### Quick Buttons

- Built-in Button entities (under the device) for: Open, Close, Gap Vent, Close w/o Lock, Stop Over, Stop.
- Optional script blueprint: `blueprints/script/evotecit/siegenia_mode_button.yaml`.
  - Import via Settings → Automations & Scenes → Blueprints → Import Blueprint → paste repo URL, or copy the file into your HA `blueprints/script/...` folder.
  - Create a script from the blueprint, pick your Siegenia cover, and choose the mode. Add the script to your dashboard as a button.

## Notes

- The controller uses a self-signed TLS certificate; this integration connects with certificate verification disabled for local LAN use.
- Only a single sash (index 0) is exposed currently. Multi-sash support can be added if needed.

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
