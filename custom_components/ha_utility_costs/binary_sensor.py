"""Binary sensor platform for HA Utility Costs."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    API_STATUS_CONNECTED,
    API_STATUS_UNKNOWN,
    CONF_PROVIDER_TYPE,
    DEFAULT_STALE_HOURS,
    DOMAIN,
    PROVIDER_TYPE_ELECTRIC,
)
from .coordinator import ElectricRatesCoordinator, WaterRatesCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for HA Utility Costs."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    provider_type = entry.data.get(CONF_PROVIDER_TYPE, PROVIDER_TYPE_ELECTRIC)
    async_add_entities([RateApiProblemBinarySensor(coordinator, entry, provider_type)])


class RateApiProblemBinarySensor(
    CoordinatorEntity[ElectricRatesCoordinator | WaterRatesCoordinator],
    BinarySensorEntity,
):
    """Diagnostic binary sensor indicating backend API or stale-rate issues."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ElectricRatesCoordinator | WaterRatesCoordinator,
        entry: ConfigEntry,
        provider_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._provider_type = provider_type
        self._provider_key = coordinator.provider
        label = coordinator.provider.upper()
        type_label = "Electric" if provider_type == PROVIDER_TYPE_ELECTRIC else "Water"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"{label} {type_label} Rates",
            "manufacturer": "eratemanager",
        }

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_{self._provider_type}_api_problem"

    @property
    def name(self) -> str:
        return "API problem"

    @property
    def available(self) -> bool:
        return True

    def _rates_age_hours(self) -> float | None:
        data = self.coordinator.data or {}
        fetched_at = data.get("fetched_at")
        if not fetched_at:
            return None
        try:
            dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return round((datetime.now(timezone.utc) - dt).total_seconds() / 3600.0, 2)
        except Exception:
            return None

    @property
    def is_on(self) -> bool:
        status = getattr(self.coordinator, "api_status", API_STATUS_UNKNOWN)
        if status not in (API_STATUS_CONNECTED, API_STATUS_UNKNOWN):
            return True
        if not self.coordinator.last_update_success:
            return True
        age = self._rates_age_hours()
        if age is not None and age > DEFAULT_STALE_HOURS:
            return True
        return False

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "api_status": getattr(self.coordinator, "api_status", API_STATUS_UNKNOWN),
            "rates_age_hours": self._rates_age_hours(),
            "stale_threshold_hours": DEFAULT_STALE_HOURS,
            "last_error": getattr(self.coordinator, "_last_error_message", None),
        }
