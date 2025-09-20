# Support and Troubleshooting

When filing issues, please include:
- Home Assistant version (e.g., 2025.9.0), Supervisor/Core.
- Integration version (see `custom_components/siegenia/manifest.json`).
- Device details: model (e.g., MHS400 Schema A), firmware, IP, number of sashes.
- Reproduction steps and what you expected vs. saw.
- Relevant logs and diagnostics (see below).

## Enable Debug Logs
Add to `configuration.yaml` (temporarily):

```
logger:
  default: info
  logs:
    custom_components.siegenia: debug
```

Restart HA; reproduce the issue; then attach the log lines.

## Attach Diagnostics
- Settings → Devices & Services → Siegenia → 3‑dot menu → Download diagnostics.
- This JSON redacts credentials but shows the device payload and current state.

## Network/Connectivity
- Device must be reachable on your LAN; ensure your firewall allows TLS (default 443).
- The controller uses a self‑signed certificate; connection is local only.

## Known Quirks
- During motion started manually (no recent HA command), the Mode shows the last stable state and `sensor.operation_source` reports `MANUAL`.
- Brand images rely on the Home Assistant Brands repo; we serve local PNGs as a fallback while the PR is pending.

## Getting Faster Help
- Include exact timestamps from Logbook for actions.
- If you can, capture a short debug log covering: integration startup, one command, and the resulting push update.
