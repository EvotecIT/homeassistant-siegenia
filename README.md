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

## Notes

- The controller uses a self-signed TLS certificate; this integration connects with certificate verification disabled for local LAN use.
- Only a single sash (index 0) is exposed currently. Multi-sash support can be added if needed.

## Credits

- Inspiration and protocol reference: Homebridge plugin and Siegenia.NET by the repo author.

