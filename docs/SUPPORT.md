# Support and Troubleshooting

[Back to the README](../README.md) · [Configuration](configuration.md)

Reproduce the problem once, then download diagnostics before reloading the
integration. When filing an issue, include:

- Home Assistant version and installation type.
- Integration version (see `custom_components/siegenia/manifest.json`).
- Controller model (for example, MHS400 Schema A), firmware, and number of sashes.
- Reproduction steps and what you expected vs. saw.
- Relevant logs and diagnostics (see below).

## Enable Debug Logs

If diagnostics are not enough, enable the integration logger temporarily in
`configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.siegenia: debug
```

Restart Home Assistant, reproduce the issue, and turn debug logging off again.
Review log lines before attaching them; remove credentials, private addresses,
and other personal information.

## Attach Diagnostics

- Settings → Devices & Services → Siegenia → 3‑dot menu → Download diagnostics.
- The JSON redacts credentials but contains device payload and current state.
  Review it before posting publicly.

## Network/Connectivity

- Device must be reachable on your LAN; ensure your firewall allows TLS (default 443).
- The controller uses a self‑signed certificate; connection is local only.

## Known Quirks

- During motion started manually (no recent HA command), the Mode shows the last stable state and `sensor.operation_source` reports `MANUAL`.

## Getting Faster Help

- Include exact timestamps from Logbook for actions.
- If you can, capture a short debug log covering: integration startup, one command, and the resulting push update.
