"""Data update coordinators for HA Utility Costs."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, CONF_API_URL, CONF_API_TOKEN, CONF_PROVIDER, CONF_PROVIDER_TYPE

LOGGER = logging.getLogger(__name__)
DEFAULT_SCAN_INTERVAL = 900  # seconds


class ElectricRatesCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch electric rates from the eRateManager backend."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.api_url: str = entry.data[CONF_API_URL].rstrip("/")
        self.api_token: str | None = entry.data.get(CONF_API_TOKEN)
        self.provider: str = entry.data[CONF_PROVIDER]

        super().__init__(
            hass,
            LOGGER,
            name=f"Electric Rates ({self.provider})",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        url = f"{self.api_url}/rates/{self.provider}/residential"
        session = aiohttp_client.async_get_clientsession(self.hass)
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status} from {url}")
                data = await resp.json()
        except Exception as err:
            raise UpdateFailed(f"Error fetching {url}: {err}") from err

        if not isinstance(data, dict):
            raise UpdateFailed("Response is not a JSON object")

        return data


class WaterRatesCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch water rates from the eRateManager backend."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.api_url: str = entry.data[CONF_API_URL].rstrip("/")
        self.api_token: str | None = entry.data.get(CONF_API_TOKEN)
        self.provider: str = entry.data[CONF_PROVIDER]

        super().__init__(
            hass,
            LOGGER,
            name=f"Water Rates ({self.provider})",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        url = f"{self.api_url}/water/rates/{self.provider}"
        session = aiohttp_client.async_get_clientsession(self.hass)
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status} from {url}")
                data = await resp.json()
        except Exception as err:
            raise UpdateFailed(f"Error fetching {url}: {err}") from err

        if not isinstance(data, dict):
            raise UpdateFailed("Response is not a JSON object")

        return data
