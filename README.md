# Siegenia for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![CI](https://img.shields.io/github/actions/workflow/status/EvotecIT/homeassistant-siegenia/ci.yml?branch=master&style=for-the-badge&label=CI)](https://github.com/EvotecIT/homeassistant-siegenia/actions/workflows/ci.yml)
[![Hassfest](https://img.shields.io/github/actions/workflow/status/EvotecIT/homeassistant-siegenia/hassfest.yml?branch=master&style=for-the-badge&label=Hassfest)](https://github.com/EvotecIT/homeassistant-siegenia/actions/workflows/hassfest.yml)

Local Siegenia support for Home Assistant, focused on MHS-family controllers and a practical, polished Home Assistant experience.

![Siegenia integration overview](assets/screenshots/integration-overview.png)

## 🎯 What This Is

This custom integration connects Siegenia window controllers to Home Assistant using the local device API.

It is designed to be:

- local and private
- responsive
- GUI-configurable
- friendly for dashboards, automations, and daily use

## ✨ What You Get

- config flow setup
- cover control for open, close, stop, and mode-style actions
- sensors, binary sensors, update entity, buttons, numbers, and selects
- device automations and helpful services
- diagnostics and push-style behavior where available

## 🏠 Installation

### HACS

1. Open HACS.
2. Add this repository as a custom repository of type `Integration`.
3. Install `Siegenia`.
4. Restart Home Assistant.
5. Add `Siegenia` from `Settings -> Devices & services`.

### Manual

1. Copy the `custom_components/siegenia` folder into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from `Settings -> Devices & services`.

## ⚙️ Configuration

You will usually need:

- host or IP
- username
- password
- default secure WebSocket connection settings

The integration also includes options for reconnect behavior, discovery helpers, polling, heartbeat, warnings, and dashboard-oriented behavior.

## 🪟 Main Features

- window control through Home Assistant `cover`
- extra mode actions such as gap vent, close without lock, and stop over
- optional opening lock behavior
- timer support
- warning events and notifications
- blueprints and dashboard examples

## 🧱 Reusable Python Package

This repository now ships two usable layers:

- `siegenia_client` for direct Python access to the local Siegenia controller API
- the Home Assistant integration in `custom_components/siegenia`

Example:

```python
from siegenia_client import SiegeniaClient

client = SiegeniaClient("192.168.1.30")
```

That keeps the local protocol layer reusable for scripts or tooling while the Home Assistant integration stays focused on setup, entities, and automations.

## 🛠️ Development

```bash
pip install -r requirements_test.txt
pytest
```

There is also a latest-stack test path documented in the repo for newer Home Assistant and Python versions.

## ❤️ Support

- Support notes: `docs/SUPPORT.md`
- Releasing notes: `docs/RELEASING.md`
- Source: [GitHub Repository](https://github.com/EvotecIT/homeassistant-siegenia)
