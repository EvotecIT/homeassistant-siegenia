import asyncio


async def test_push_slows_poll_and_fires_event(hass, setup_integration):
    entry = setup_integration
    coordinator = hass.data[entry.domain][entry.entry_id]

    # Initially default interval
    default_int = coordinator._default_interval  # noqa: SLF001

    # Simulate push
    if hasattr(coordinator.client, "push_cb"):
        coordinator.client.push_cb({"command": "getDeviceParams", "data": {"states": {"0": "OPEN"}, "warnings": ["Test"]}})
    else:
        # Call internal handler as fallback
        coordinator._handle_push_update({"command": "getDeviceParams", "data": {"states": {"0": "OPEN"}, "warnings": ["Test"]}})  # noqa: SLF001

    # Coordinator should switch to push interval
    assert coordinator.update_interval != default_int

    # Listen for event
    events = []
    hass.bus.async_listen_once("siegenia_warning", lambda e: events.append(e))
    await asyncio.sleep(0)  # let loop process
    assert events, "Expected siegenia_warning event on push with warnings"

