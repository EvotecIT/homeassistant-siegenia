# Siegenia Python Library

`siegenia_client` is the reusable async Python layer that powers the Home Assistant integration in this repository.

It is intended for:

- local troubleshooting tools
- custom scripts
- future native clients on other platforms
- integration tests that need direct controller access

## Installation

From this repository:

```bash
python -m pip install -e .
```

## Quick Start

```python
import asyncio

from siegenia_client import SiegeniaClient


async def main() -> None:
    client = SiegeniaClient("192.168.1.30")
    await client.connect()
    try:
        await client.login("admin", "secret")
        device = await client.get_device()
        print(device)
    finally:
        await client.disconnect()


asyncio.run(main())
```

## Main Workflow

Typical usage looks like this:

1. Create `SiegeniaClient(host, ...)`
2. Call `connect()`
3. Call `login(user, password)`
4. Read state or send actions
5. Call `disconnect()` when done

## Main Read Methods

- `get_device()`
- `get_device_params()`
- `get_device_details()`

## Main Write / Action Methods

- `set_device_params(params)`
- `open_close(sash, action)`
- `stop(sash)`
- `reset_device()`
- `reboot_device()`
- `renew_cert()`

## Connection Helpers

- `connect()`
- `disconnect()`
- `keep_alive()`
- `start_heartbeat(interval=10.0)`
- `set_push_callback(callback)`

## Error Handling

The library exposes:

- `SiegeniaError`: base exception
- `AuthenticationError`: login/authentication failure

## Notes

- The client uses the local secure WebSocket endpoint exposed by supported Siegenia controllers.
- The Home Assistant integration in `custom_components/siegenia` is built on top of this package.
