# Siegenia for Home Assistant

![Siegenia for Home Assistant](assets/homeassistant-siegenia-social.png)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![CI](https://img.shields.io/github/actions/workflow/status/EvotecIT/homeassistant-siegenia/ci.yml?branch=master&style=for-the-badge&label=CI)](https://github.com/EvotecIT/homeassistant-siegenia/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/EvotecIT/homeassistant-siegenia?style=for-the-badge)](LICENSE)

## Overview

Connect supported Siegenia window controllers to Home Assistant over your local
network. The integration focuses on MHS-family controllers and exposes windows
as `cover` entities.

- Open, close, stop, gap ventilation, and other supported window modes.
- Timers, opening-lock behavior, and device settings.
- Warning events, notifications, dashboard examples, and automation blueprints.

Available modes depend on the controller. Keep moving windows supervised and
test any automation with the opening area clear.

## Sponsor

Support development and maintenance through
[GitHub Sponsors](https://github.com/sponsors/PrzemyslawKlys).
Sponsorship is optional; these projects remain open source.

## More for your Home Assistant home

Other integrations and dashboards we maintain:

- [Dreame & MOVA mowers](https://github.com/EvotecIT/homeassistant-dreamelawnmower) — Mowing controls, maps, schedules, and supported cameras.
- [Lawn Mower Card](https://github.com/EvotecIT/lovelace-lawn-mower-card) — A dashboard for mower state, maps, and controls.
- [KEF](https://github.com/EvotecIT/homeassistant-kef) — Local control for modern and legacy speaker families.
- [Devialet](https://github.com/EvotecIT/homeassistant-devialet) — Local speaker control, with Dione support.
- [EasyControlX](https://github.com/EvotecIT/homeassistant-easycontrolx) — Connect supported Windows and macOS hosts.

For a native app connected to the same Home Assistant setup:

- [CasaRay](https://casaray.dev/) — rooms, devices, cameras, and home activity on
  iPhone, iPad, and Mac.
- [Tactra Remote](https://tactra.dev/) — media players, speakers, and TV controls
  on iPhone, iPad, Apple Watch, and Mac.

Neither app is required to use this project.

## Installation

### HACS

[![Open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=EvotecIT&repository=homeassistant-siegenia&category=integration)

1. Open the repository with the button above. Alternatively, in HACS choose
   **Custom repositories**, add `https://github.com/EvotecIT/homeassistant-siegenia`,
   and select **Integration**.
2. Download **Siegenia** and restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**, then choose
   **Siegenia**.

### Manual

1. Download the repository and copy `custom_components/siegenia` into your
   Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Add **Siegenia** from **Settings → Devices & services**.

## Configuration

Enter the controller's host/IP, username, and password. Secure WebSockets
(`wss`, port **443**) are the default. Use certificate verification when the
certificate and hostname are trusted; otherwise keep the self-signed controller
and Home Assistant on a trusted local network.

Open **Configure** to adjust polling, heartbeat, warnings, and optional dashboard
controls. Start with the defaults, then test the available modes while the
window area is clear.

## Documentation

| I want to… | Guide |
| --- | --- |
| Configure connection and window behavior | [Configuration](docs/configuration.md) |
| Add a dashboard, timer, or automation | [Automations and dashboards](docs/automations.md) |
| Diagnose a connection or command failure | [Support and troubleshooting](docs/SUPPORT.md) |
| Use the controller from Python | [Python library](docs/python-library.md) |
| Contribute or release an update | [Development](docs/development.md) · [Releasing](docs/RELEASING.md) |

## Screenshots

![Siegenia integration overview](assets/screenshots/integration-overview.png)

## Support

[Report an issue](https://github.com/EvotecIT/homeassistant-siegenia/issues)
with the controller model, firmware, number of sashes, integration version, and
steps to reproduce. Attach diagnostics after reviewing them for personal
information. Never post controller credentials.
