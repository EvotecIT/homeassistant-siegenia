from copy import deepcopy

from custom_components.siegenia.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_credentials(hass, setup_integration):
    entry = setup_integration
    coordinator = entry.runtime_data
    coordinator.device_info["data"].update(
        devicelocation="Private room", devicefloor="Private floor"
    )
    before = deepcopy((dict(entry.data), coordinator.device_info, coordinator.data))
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["entry"]["data"]["username"] == "**REDACTED**"
    assert data["entry"]["data"]["password"] == "**REDACTED**"
    assert data["entry"]["data"]["host"] == "**REDACTED**"
    for key in ("serialnr", "devicename", "devicelocation", "devicefloor"):
        assert data["device_info"]["data"][key] == "**REDACTED**"
    assert data["device_info"]["data"]["type"] == 6
    assert data["device_info"]["data"]["softwareversion"] == "1.7.2"
    assert data["last_params"]["data"]["states"] == {"0": "CLOSED"}
    assert (dict(entry.data), coordinator.device_info, coordinator.data) == before
