# Configuration

[Back to the README](../README.md) · [Troubleshooting](SUPPORT.md)

## Connection

Add **Siegenia** from **Settings → Devices & services** and enter the
controller's host/IP, username, and password.

| Setting | Default |
| --- | --- |
| Protocol | Secure WebSocket (`wss`) |
| Port | `443` |
| Certificate verification | Off, for controllers using self-signed certificates |
| Polling interval | 5 seconds |
| Heartbeat interval | 10 seconds |
| Automatic and extended discovery | Off; opt in only when needed |

Enable certificate verification when the controller certificate and hostname
are trusted. Without verification, keep the controller and Home Assistant on
a trusted local network. Do not expose the controller API to the internet.

If credentials change, use Home Assistant's reauthentication flow. The
`siegenia.set_connection` action can update the host, port, or protocol;
it does not replace the credential flow.

## Window controls

The main `cover` entity exposes supported open, close, and stop actions.
Additional modes can include gap ventilation, close without locking, and
stop-over. Choose modes that your controller supports.

The position slider represents discrete controller modes as percentages. It is
not a measurement of the physical opening. Configure its thresholds only if you
understand how you want those modes represented on your dashboard.

## Options

Open the integration's **Configure** dialog to choose optional state sensors,
opening counts, buttons, the position slider, opening prevention, and warning
behavior. Advanced timing options distinguish moving and idle polling.

Start with defaults. Changing several connection and timing settings at once
makes intermittent problems harder to diagnose.

## Offline behavior

When the controller disconnects, its entities become unavailable. Commands fail
rather than being reported as successful, and entities recover after the
connection returns.

For manually initiated movement, the displayed mode can remain at the last
stable state while the operation-source sensor reports manual control.

## Timers and automations

Use [automations and dashboards](automations.md) for normal cover actions,
explicit mode commands, and timers. Keep the window area clear and test any
automation under supervision before enabling it.
