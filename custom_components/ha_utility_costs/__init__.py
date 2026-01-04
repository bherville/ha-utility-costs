"""HA Utility Costs integration for Home Assistant."""
from __future__ import annotations

import logging
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

_LOGGER = logging.getLogger(__name__)

# Platforms to load
PLATFORMS: list[str] = ["sensor"]

# This integration is config entry only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via YAML (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Utility Costs from a config entry."""
    _LOGGER.info("Setting up HA Utility Costs for provider: %s", entry.data.get(CONF_PROVIDER_TYPE, PROVIDER_TYPE_ELECTRIC))
    provider_type = entry.data.get(CONF_PROVIDER_TYPE, PROVIDER_TYPE_ELECTRIC)

    # Create the appropriate coordinator based on provider type
    if provider_type == PROVIDER_TYPE_WATER:
        coordinator = WaterRatesCoordinator(hass, entry)
    else:
        coordinator = ElectricRatesCoordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Error during first refresh: %s", err)
        raise

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("HA Utility Costs setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
