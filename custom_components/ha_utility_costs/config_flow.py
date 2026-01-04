"""Config flow for HA Utility Costs."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, selector

from .const import (
    DOMAIN,
    CONF_API_URL,
    CONF_API_TOKEN,
    CONF_PROVIDER,
    CONF_PROVIDER_TYPE,
    PROVIDER_TYPE_ELECTRIC,
    PROVIDER_TYPE_WATER,
    STATIC_ELECTRIC_PROVIDERS,
    STATIC_WATER_PROVIDERS,
)

_LOGGER = logging.getLogger(__name__)


async def _fetch_electric_providers(hass, api_url: str, api_token: str | None = None) -> dict[str, str]:
    """Fetch electric providers from the backend /providers endpoint."""
    api_url = api_url.rstrip("/")
    url = f"{api_url}/providers"
    session = aiohttp_client.async_get_clientsession(hass)
    headers = {"User-Agent": "ha-utility-costs/1.0"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    try:
        async with session.get(url, headers=headers, timeout=10) as resp:
            if resp.status == 401:
                raise ValueError("Unauthorized - check your API token")
            if resp.status == 404:
                raise ValueError("API endpoint not found - check your API URL")
            if resp.status != 200:
                raise ValueError(f"HTTP {resp.status}: {resp.reason}")
            data = await resp.json()
    except ValueError:
        raise
    except Exception as err:
        _LOGGER.warning("Failed to fetch electric providers from %s: %s", url, err)
        raise ValueError(f"Connection error: {type(err).__name__}: {err}")

    providers: dict[str, str] = {}
    items = data.get("providers") or []
    for item in items:
        key = item.get("key")
        name = item.get("name") or key
        if key:
            providers[name] = key

    if not providers:
        return STATIC_ELECTRIC_PROVIDERS.copy()

    return providers


async def _fetch_water_providers(hass, api_url: str, api_token: str | None = None) -> dict[str, str]:
    """Fetch water providers from the backend /water/providers endpoint."""
    api_url = api_url.rstrip("/")
    url = f"{api_url}/water/providers"
    session = aiohttp_client.async_get_clientsession(hass)
    headers = {"User-Agent": "ha-utility-costs/1.0"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    try:
        async with session.get(url, headers=headers, timeout=10) as resp:
            if resp.status == 401:
                raise ValueError("Unauthorized - check your API token")
            if resp.status == 404:
                raise ValueError("API endpoint not found - check your API URL")
            if resp.status != 200:
                raise ValueError(f"HTTP {resp.status}: {resp.reason}")
            data = await resp.json()
    except ValueError:
        raise
    except Exception as err:
        _LOGGER.warning("Failed to fetch water providers from %s: %s", url, err)
        raise ValueError(f"Connection error: {type(err).__name__}: {err}")

    providers: dict[str, str] = {}
    items = data.get("providers") or []
    for item in items:
        key = item.get("key")
        name = item.get("name") or key
        if key:
            providers[name] = key

    if not providers:
        return STATIC_WATER_PROVIDERS.copy()

    return providers


async def _validate_electric_provider(hass, api_url: str, provider_key: str, api_token: str | None = None) -> dict:
    """Validate that /rates/electric/{provider}/residential works."""
    api_url = api_url.rstrip("/")
    url = f"{api_url}/rates/electric/{provider_key}/residential"
    session = aiohttp_client.async_get_clientsession(hass)
    headers = {"User-Agent": "ha-utility-costs/1.0"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    _LOGGER.debug("Validating electric provider at: %s", url)

    try:
        async with session.get(url, headers=headers, timeout=10) as resp:
            _LOGGER.debug("Response status: %s", resp.status)
            if resp.status == 401:
                raise ValueError("Unauthorized - check your API token")
            if resp.status == 404:
                raise ValueError(f"Provider '{provider_key}' not found on backend")
            if resp.status != 200:
                raise ValueError(f"Backend returned HTTP {resp.status}: {resp.reason}")
            data = await resp.json()
    except ValueError:
        raise
    except Exception as err:
        _LOGGER.error("Connection error validating provider: %s", err)
        raise ValueError(f"Connection error: {type(err).__name__}: {err}")

    if "rates" not in data:
        raise ValueError("Response missing 'rates' key - backend may not support this provider")

    return {
        "title": f"Electric Rates ({provider_key.upper()})",
        "utility": data.get("utility"),
    }


async def _validate_water_provider(hass, api_url: str, provider_key: str, api_token: str | None = None) -> dict:
    """Validate that /water/rates/{provider} works."""
    api_url = api_url.rstrip("/")
    url = f"{api_url}/water/rates/{provider_key}"
    session = aiohttp_client.async_get_clientsession(hass)
    headers = {"User-Agent": "ha-utility-costs/1.0"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    try:
        async with session.get(url, headers=headers, timeout=10) as resp:
            if resp.status == 401:
                raise ValueError("Unauthorized - check your API token")
            if resp.status == 404:
                raise ValueError(f"Provider '{provider_key}' not found on backend")
            if resp.status != 200:
                raise ValueError(f"Backend returned HTTP {resp.status}: {resp.reason}")
            data = await resp.json()
    except ValueError:
        raise
    except Exception as err:
        raise ValueError(f"Connection error: {type(err).__name__}: {err}")

    if "water" not in data:
        raise ValueError("Response missing 'water' key - backend may not support this provider")

    return {
        "title": f"Water Rates ({provider_key.upper()})",
        "provider_name": data.get("provider_name"),
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for HA Utility Costs."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_url: str | None = None
        self._api_token: str | None = None
        self._provider_type: str | None = None
        self._providers: dict[str, str] = {}

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Step 1: Get API URL and utility type."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_url = user_input[CONF_API_URL]
            self._api_token = user_input.get(CONF_API_TOKEN)
            self._provider_type = user_input[CONF_PROVIDER_TYPE]

            # Fetch providers based on type
            try:
                if self._provider_type == PROVIDER_TYPE_ELECTRIC:
                    self._providers = await _fetch_electric_providers(
                        self.hass, self._api_url, self._api_token
                    )
                else:
                    self._providers = await _fetch_water_providers(
                        self.hass, self._api_url, self._api_token
                    )
            except ValueError as err:
                _LOGGER.error("Failed to fetch providers: %s", err)
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_API_URL, default=self._api_url or "https://rates.bherville.com"): str,
                            vol.Required(CONF_API_TOKEN, default=self._api_token or ""): str,
                            vol.Required(CONF_PROVIDER_TYPE, default=self._provider_type or PROVIDER_TYPE_ELECTRIC): vol.In(
                                {
                                    PROVIDER_TYPE_ELECTRIC: "Electric",
                                    PROVIDER_TYPE_WATER: "Water",
                                }
                            ),
                        }
                    ),
                    errors=errors,
                    description_placeholders={"error_details": str(err)},
                )
            except Exception as err:
                _LOGGER.exception("Unexpected error fetching providers")
                if self._provider_type == PROVIDER_TYPE_ELECTRIC:
                    self._providers = STATIC_ELECTRIC_PROVIDERS.copy()
                else:
                    self._providers = STATIC_WATER_PROVIDERS.copy()

            return await self.async_step_provider()

        schema = vol.Schema(
            {
                vol.Required(CONF_API_URL, default="https://rates.bherville.com"): str,
                vol.Required(CONF_API_TOKEN): str,
                vol.Required(CONF_PROVIDER_TYPE, default=PROVIDER_TYPE_ELECTRIC): vol.In(
                    {
                        PROVIDER_TYPE_ELECTRIC: "Electric",
                        PROVIDER_TYPE_WATER: "Water",
                    }
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_provider(self, user_input: dict | None = None) -> FlowResult:
        """Step 2: Select provider."""
        errors: dict[str, str] = {}

        if self._api_url is None or self._provider_type is None:
            return await self.async_step_user()

        if user_input is not None:
            label = user_input[CONF_PROVIDER]
            provider_key = self._providers.get(label)
            if not provider_key:
                errors["base"] = "invalid_provider"
            else:
                try:
                    if self._provider_type == PROVIDER_TYPE_ELECTRIC:
                        info = await _validate_electric_provider(
                            self.hass, self._api_url, provider_key, self._api_token
                        )
                    else:
                        info = await _validate_water_provider(
                            self.hass, self._api_url, provider_key, self._api_token
                        )
                except Exception as err:
                    _LOGGER.exception("Error connecting to provider: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    # Unique per provider+type+api_url
                    await self.async_set_unique_id(
                        f"{self._provider_type}_{provider_key}_{self._api_url}"
                    )
                    self._abort_if_unique_id_configured()

                    data = {
                        CONF_API_URL: self._api_url,
                        CONF_PROVIDER: provider_key,
                        CONF_PROVIDER_TYPE: self._provider_type,
                    }
                    if self._api_token:
                        data[CONF_API_TOKEN] = self._api_token
                    return self.async_create_entry(title=info["title"], data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_PROVIDER): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(self._providers.keys()),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="provider", data_schema=schema, errors=errors)
