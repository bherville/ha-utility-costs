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

# Refresh interval configuration
CONF_REFRESH_INTERVAL = "refresh_interval"
DEFAULT_REFRESH_INTERVAL = 3600  # 1 hour in seconds
MIN_REFRESH_INTERVAL = 300  # 5 minutes minimum
MAX_REFRESH_INTERVAL = 86400  # 24 hours maximum

# Tracked device entity options (electric entries)
CONF_TRACKED_ENERGY_ENTITIES = "tracked_energy_entities"
CONF_TRACKED_POWER_ENTITIES = "tracked_power_entities"

DEFAULT_STALE_HOURS = 48.0
HOURS_PER_MONTH = 730.0

# API status values for diagnostic sensor
API_STATUS_CONNECTED = "connected"
API_STATUS_AUTH_FAILED = "auth_failed"
API_STATUS_UNREACHABLE = "unreachable"
API_STATUS_RATE_LIMITED = "rate_limited"
API_STATUS_UNKNOWN = "unknown"

# Service names
SERVICE_FORCE_REFRESH = "force_refresh"

# Fallback providers if /providers endpoint is unavailable
STATIC_ELECTRIC_PROVIDERS: dict[str, str] = {
    "CEMC": "cemc",
    "NES": "nes",
    "KUB": "kub",
}

STATIC_WATER_PROVIDERS: dict[str, str] = {
    "WHUD": "whud",
}
