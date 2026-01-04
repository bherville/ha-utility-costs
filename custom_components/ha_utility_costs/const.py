"""Constants for HA Utility Costs integration."""
from __future__ import annotations

DOMAIN = "ha_utility_costs"
DEFAULT_NAME = "HA Utility Costs"

CONF_API_URL = "api_url"
CONF_API_TOKEN = "api_token"
CONF_PROVIDER = "provider"
CONF_PROVIDER_TYPE = "provider_type"

# Provider types
PROVIDER_TYPE_ELECTRIC = "electric"
PROVIDER_TYPE_WATER = "water"

# Fallback providers if /providers endpoint is unavailable
STATIC_ELECTRIC_PROVIDERS: dict[str, str] = {
    "CEMC": "cemc",
    "NES": "nes",
    "KUB": "kub",
}

STATIC_WATER_PROVIDERS: dict[str, str] = {
    "WHUD": "whud",
}
