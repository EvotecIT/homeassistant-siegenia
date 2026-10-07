"""Typed runtime ownership for a Siegenia config entry."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import SiegeniaDataUpdateCoordinator

type SiegeniaConfigEntry = ConfigEntry[SiegeniaDataUpdateCoordinator]
