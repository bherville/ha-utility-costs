"""Data update coordinators for HA Utility Costs."""
from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import aiohttp_client

from .const import (
    DOMAIN,
    CONF_API_URL,
    CONF_API_TOKEN,
    CONF_PROVIDER,
    CONF_PROVIDER_TYPE,
    CONF_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    API_STATUS_CONNECTED,
    API_STATUS_AUTH_FAILED,
    API_STATUS_UNREACHABLE,
    API_STATUS_RATE_LIMITED,
    API_STATUS_UNKNOWN,
    PROVIDER_TYPE_ELECTRIC,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_SCAN_INTERVAL = 900  # seconds (fallback)


class ElectricRatesCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch electric rates from the eRateManager backend."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.api_url: str = entry.data[CONF_API_URL].rstrip("/")
        self.api_token: str | None = entry.data.get(CONF_API_TOKEN)
        self.provider: str = entry.data[CONF_PROVIDER]
        self.api_status: str = API_STATUS_UNKNOWN
        self._last_error_message: str | None = None

        # Get refresh interval from options, fall back to default
        refresh_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)

        super().__init__(
            hass,
            LOGGER,
            name=f"Electric Rates ({self.provider})",
            update_interval=timedelta(seconds=refresh_interval),
        )

    def update_interval_from_options(self) -> None:
        """Update the polling interval from config entry options."""
        new_interval = self.entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
        self.update_interval = timedelta(seconds=new_interval)
        LOGGER.info("Updated refresh interval to %s seconds", new_interval)

    async def async_force_refresh(self) -> dict:
        """Force refresh by calling the backend refresh endpoint first."""
        refresh_url = f"{self.api_url}/api/v2/electric-rates/{self.provider}/refresh"
        session = aiohttp_client.async_get_clientsession(self.hass, verify_ssl=False)
        headers = {"User-Agent": "ha-utility-costs/1.0"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        LOGGER.info("Triggering force refresh for provider %s", self.provider)

        try:
            async with session.post(refresh_url, headers=headers, timeout=120) as resp:
                if resp.status == 401:
                    self.api_status = API_STATUS_AUTH_FAILED
                    self._last_error_message = "API token expired or invalid"
                    raise UpdateFailed("API token expired or invalid - please regenerate in eratemanager")
                if resp.status == 403:
                    self.api_status = API_STATUS_AUTH_FAILED
                    self._last_error_message = "Insufficient permissions"
                    raise UpdateFailed("Insufficient permissions - check API token permissions")
                if resp.status == 429:
                    self.api_status = API_STATUS_RATE_LIMITED
                    self._last_error_message = "Rate limited"
                    raise UpdateFailed("Rate limited - please wait before refreshing again")
                if resp.status != 200:
                    LOGGER.error("Force refresh failed with HTTP %s", resp.status)
                    raise UpdateFailed(f"Force refresh failed: HTTP {resp.status}")
        except aiohttp.ClientError as err:
            self.api_status = API_STATUS_UNREACHABLE
            self._last_error_message = str(err)
            raise UpdateFailed(f"Connection error during force refresh: {err}") from err

        # Now fetch the fresh data
        return await self.async_refresh()

    async def _async_update_data(self) -> dict:
        url = f"{self.api_url}/api/v2/electric-rates/{self.provider}/residential"
        session = aiohttp_client.async_get_clientsession(self.hass, verify_ssl=False)
        headers = {"User-Agent": "ha-utility-costs/1.0"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        LOGGER.debug("Fetching electric rates from: %s", url)

        try:
            async with session.get(url, headers=headers, timeout=30) as resp:
                if resp.status == 401:
                    self.api_status = API_STATUS_AUTH_FAILED
                    self._last_error_message = "API token expired or invalid"
                    LOGGER.error("API token expired or invalid - please regenerate in eratemanager")
                    raise UpdateFailed("API token expired or invalid - please regenerate in eratemanager")
                if resp.status == 403:
                    self.api_status = API_STATUS_AUTH_FAILED
                    self._last_error_message = "Insufficient permissions"
                    LOGGER.error("Insufficient permissions - check API token permissions")
                    raise UpdateFailed("Insufficient permissions - check API token permissions")
                if resp.status == 429:
                    self.api_status = API_STATUS_RATE_LIMITED
                    self._last_error_message = "Rate limited by API"
                    LOGGER.warning("Rate limited by API")
                    raise UpdateFailed("Rate limited - please wait before refreshing again")
                if resp.status != 200:
                    self.api_status = API_STATUS_UNREACHABLE
                    self._last_error_message = f"HTTP {resp.status}"
                    LOGGER.error("HTTP %s from %s", resp.status, url)
                    raise UpdateFailed(f"HTTP {resp.status} from {url}")
                data = await resp.json()
        except UpdateFailed:
            raise
        except aiohttp.ClientError as err:
            self.api_status = API_STATUS_UNREACHABLE
            self._last_error_message = str(err)
            LOGGER.error("Connection error fetching %s: %s", url, err)
            raise UpdateFailed(f"Connection error: {err}") from err
        except Exception as err:
            self.api_status = API_STATUS_UNKNOWN
            self._last_error_message = str(err)
            LOGGER.error("Error fetching %s: %s", url, err)
            raise UpdateFailed(f"Error fetching {url}: {err}") from err

        if not isinstance(data, dict):
            self.api_status = API_STATUS_UNKNOWN
            self._last_error_message = "Response is not a JSON object"
            raise UpdateFailed("Response is not a JSON object")

        # Success!
        self.api_status = API_STATUS_CONNECTED
        self._last_error_message = None
        return data


class WaterRatesCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch water rates from the eRateManager backend."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.api_url: str = entry.data[CONF_API_URL].rstrip("/")
        self.api_token: str | None = entry.data.get(CONF_API_TOKEN)
        self.provider: str = entry.data[CONF_PROVIDER]
        self.api_status: str = API_STATUS_UNKNOWN
        self._last_error_message: str | None = None

        # Get refresh interval from options, fall back to default
        refresh_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)

        super().__init__(
            hass,
            LOGGER,
            name=f"Water Rates ({self.provider})",
            update_interval=timedelta(seconds=refresh_interval),
        )

    def update_interval_from_options(self) -> None:
        """Update the polling interval from config entry options."""
        new_interval = self.entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
        self.update_interval = timedelta(seconds=new_interval)
        LOGGER.info("Updated refresh interval to %s seconds", new_interval)

    async def async_force_refresh(self) -> dict:
        """Force refresh by calling the backend refresh endpoint first."""
        refresh_url = f"{self.api_url}/api/v2/water-rates/{self.provider}/refresh"
        session = aiohttp_client.async_get_clientsession(self.hass, verify_ssl=False)
        headers = {"User-Agent": "ha-utility-costs/1.0"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        LOGGER.info("Triggering force refresh for water provider %s", self.provider)

        try:
            async with session.post(refresh_url, headers=headers, timeout=120) as resp:
                if resp.status == 401:
                    self.api_status = API_STATUS_AUTH_FAILED
                    self._last_error_message = "API token expired or invalid"
                    raise UpdateFailed("API token expired or invalid - please regenerate in eratemanager")
                if resp.status == 403:
                    self.api_status = API_STATUS_AUTH_FAILED
                    self._last_error_message = "Insufficient permissions"
                    raise UpdateFailed("Insufficient permissions - check API token permissions")
                if resp.status == 429:
                    self.api_status = API_STATUS_RATE_LIMITED
                    self._last_error_message = "Rate limited"
                    raise UpdateFailed("Rate limited - please wait before refreshing again")
                if resp.status != 200:
                    LOGGER.error("Force refresh failed with HTTP %s", resp.status)
                    raise UpdateFailed(f"Force refresh failed: HTTP {resp.status}")
        except aiohttp.ClientError as err:
            self.api_status = API_STATUS_UNREACHABLE
            self._last_error_message = str(err)
            raise UpdateFailed(f"Connection error during force refresh: {err}") from err

        # Now fetch the fresh data
        return await self.async_refresh()

    async def _async_update_data(self) -> dict:
        url = f"{self.api_url}/api/v2/water-rates/{self.provider}/rates"
        session = aiohttp_client.async_get_clientsession(self.hass, verify_ssl=False)
        headers = {"User-Agent": "ha-utility-costs/1.0"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        LOGGER.debug("Fetching water rates from: %s", url)

        try:
            async with session.get(url, headers=headers, timeout=30) as resp:
                if resp.status == 401:
                    self.api_status = API_STATUS_AUTH_FAILED
                    self._last_error_message = "API token expired or invalid"
                    LOGGER.error("API token expired or invalid - please regenerate in eratemanager")
                    raise UpdateFailed("API token expired or invalid - please regenerate in eratemanager")
                if resp.status == 403:
                    self.api_status = API_STATUS_AUTH_FAILED
                    self._last_error_message = "Insufficient permissions"
                    LOGGER.error("Insufficient permissions - check API token permissions")
                    raise UpdateFailed("Insufficient permissions - check API token permissions")
                if resp.status == 429:
                    self.api_status = API_STATUS_RATE_LIMITED
                    self._last_error_message = "Rate limited by API"
                    LOGGER.warning("Rate limited by API")
                    raise UpdateFailed("Rate limited - please wait before refreshing again")
                if resp.status != 200:
                    self.api_status = API_STATUS_UNREACHABLE
                    self._last_error_message = f"HTTP {resp.status}"
                    LOGGER.error("HTTP %s from %s", resp.status, url)
                    raise UpdateFailed(f"HTTP {resp.status} from {url}")
                data = await resp.json()
        except UpdateFailed:
            raise
        except aiohttp.ClientError as err:
            self.api_status = API_STATUS_UNREACHABLE
            self._last_error_message = str(err)
            LOGGER.error("Connection error fetching %s: %s", url, err)
            raise UpdateFailed(f"Connection error: {err}") from err
        except Exception as err:
            self.api_status = API_STATUS_UNKNOWN
            self._last_error_message = str(err)
            LOGGER.error("Error fetching %s: %s", url, err)
            raise UpdateFailed(f"Error fetching {url}: {err}") from err

        if not isinstance(data, dict):
            self.api_status = API_STATUS_UNKNOWN
            self._last_error_message = "Response is not a JSON object"
            raise UpdateFailed("Response is not a JSON object")

        # Success!
        self.api_status = API_STATUS_CONNECTED
        self._last_error_message = None
        return data
