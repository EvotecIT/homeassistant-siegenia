from custom_components.siegenia.const import DOMAIN
from custom_components.siegenia.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_credentials(hass, setup_integration):
    entry = setup_integration
    data = await async_get_config_entry_diagnostics(hass, entry)
    # Ensure creds are redacted
    assert data["entry"]["data"]["username"] != entry.data["username"]
    assert data["entry"]["data"]["password"] != entry.data["password"]
