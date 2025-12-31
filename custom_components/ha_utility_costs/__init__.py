"""HA Utility Costs integration for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_PROVIDER_TYPE,
    PROVIDER_TYPE_ELECTRIC,
    PROVIDER_TYPE_WATER,
)
from .coordinator import ElectricRatesCoordinator, WaterRatesCoordinator

# Platforms to load
PLATFORMS: list[str] = ["sensor"]

# This integration is config entry only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via YAML (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Utility Costs from a config entry."""
    provider_type = entry.data.get(CONF_PROVIDER_TYPE, PROVIDER_TYPE_ELECTRIC)

    # Create the appropriate coordinator based on provider type
    if provider_type == PROVIDER_TYPE_WATER:
        coordinator = WaterRatesCoordinator(hass, entry)
    else:
        coordinator = ElectricRatesCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
