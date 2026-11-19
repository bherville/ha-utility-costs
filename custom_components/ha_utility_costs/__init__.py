"""HA Utility Costs integration for Home Assistant."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_PROVIDER_TYPE,
    PROVIDER_TYPE_ELECTRIC,
    PROVIDER_TYPE_WATER,
    SERVICE_FORCE_REFRESH,
)
from .coordinator import ElectricRatesCoordinator, WaterRatesCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms to load
PLATFORMS: list[str] = ["sensor", "binary_sensor"]

# This integration is config entry only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Service schema
SERVICE_FORCE_REFRESH_SCHEMA = vol.Schema({
    vol.Required("entry_id"): cv.string,
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via YAML (not used)."""
    hass.data.setdefault(DOMAIN, {})

    async def handle_force_refresh(call: ServiceCall) -> None:
        """Handle the force_refresh service call."""
        entry_id = call.data["entry_id"]
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if coordinator is None:
            raise HomeAssistantError(f"No integration found with entry_id: {entry_id}")

        _LOGGER.info("Force refresh requested for entry: %s", entry_id)
        try:
            await coordinator.async_force_refresh()
        except Exception as err:
            _LOGGER.error("Force refresh failed: %s", err)
            raise HomeAssistantError(f"Force refresh failed: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_REFRESH,
        handle_force_refresh,
        schema=SERVICE_FORCE_REFRESH_SCHEMA,
    )

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

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("HA Utility Costs setup completed successfully")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change so tracked device entities update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
