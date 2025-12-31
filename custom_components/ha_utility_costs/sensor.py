"""Sensor entities for HA Utility Costs."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_PROVIDER_TYPE,
    PROVIDER_TYPE_ELECTRIC,
    PROVIDER_TYPE_WATER,
)
from .coordinator import ElectricRatesCoordinator, WaterRatesCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for utility costs."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    provider_type = entry.data.get(CONF_PROVIDER_TYPE, PROVIDER_TYPE_ELECTRIC)

    entities: list[SensorEntity] = []

    if provider_type == PROVIDER_TYPE_ELECTRIC:
        entities.extend(_create_electric_sensors(coordinator, entry))
    else:
        entities.extend(_create_water_sensors(coordinator, entry))

    async_add_entities(entities)


def _create_electric_sensors(
    coordinator: ElectricRatesCoordinator, entry: ConfigEntry
) -> list[SensorEntity]:
    """Create electric rate sensors."""
    return [
        EnergyRateSensor(coordinator, entry),
        FixedChargeSensor(coordinator, entry),
        RatesLastRefreshSensor(coordinator, entry),
        RatesAgeHoursSensor(coordinator, entry),
        EnergyPriceSensor(coordinator, entry),
        DailyFixedCostSensor(coordinator, entry),
        MonthlyFixedCostSensor(coordinator, entry),
    ]


def _create_water_sensors(
    coordinator: WaterRatesCoordinator, entry: ConfigEntry
) -> list[SensorEntity]:
    """Create water rate sensors."""
    return [
        WaterUsageRateSensor(coordinator, entry),
        WaterBaseChargeSensor(coordinator, entry),
        SewerUsageRateSensor(coordinator, entry),
        SewerBaseChargeSensor(coordinator, entry),
        WaterRatesLastRefreshSensor(coordinator, entry),
        WaterRatesAgeHoursSensor(coordinator, entry),
    ]


def _get_residential_standard(data: dict) -> dict | None:
    """Extract residential_standard rates from electric data."""
    rates = data.get("rates") or {}
    rs = rates.get("residential_standard") or {}
    if not rs.get("is_present"):
        return None
    return rs


# =============================================================================
# Base Classes
# =============================================================================


class BaseElectricSensor(CoordinatorEntity[ElectricRatesCoordinator], SensorEntity):
    """Base class for electric rate sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ElectricRatesCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        provider = coordinator.provider
        self._provider_key = provider
        self._provider_label = provider.upper()
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"{self._provider_label} Electric Rates",
            "manufacturer": "eratemanager",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class BaseWaterSensor(CoordinatorEntity[WaterRatesCoordinator], SensorEntity):
    """Base class for water rate sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WaterRatesCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        provider = coordinator.provider
        self._provider_key = provider
        self._provider_label = provider.upper()
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"{self._provider_label} Water Rates",
            "manufacturer": "eratemanager",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


# =============================================================================
# Electric Sensors
# =============================================================================


class EnergyRateSensor(BaseElectricSensor):
    """Sensor for total energy rate (energy + fuel) in USD/kWh."""

    _attr_native_unit_of_measurement = "USD/kWh"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_total_rate"

    @property
    def name(self) -> str:
        return "Total energy rate"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        rs = _get_residential_standard(data)
        if not rs:
            return None
        energy = rs.get("energy_rate_usd_per_kwh") or 0.0
        fuel = rs.get("tva_fuel_rate_usd_per_kwh") or 0.0
        try:
            return float(energy) + float(fuel)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        rs = _get_residential_standard(data) or {}
        attrs: dict[str, object] = {}
        attrs["energy_rate_usd_per_kwh"] = rs.get("energy_rate_usd_per_kwh")
        attrs["tva_fuel_rate_usd_per_kwh"] = rs.get("tva_fuel_rate_usd_per_kwh")
        attrs["customer_charge_monthly_usd"] = rs.get("customer_charge_monthly_usd")

        fetched_at = data.get("fetched_at")
        if fetched_at:
            attrs["last_refresh"] = fetched_at
        source = data.get("source")
        if source:
            attrs["source"] = source
        source_url = data.get("source_url")
        if source_url:
            attrs["source_url"] = source_url
        pdf_url = data.get("pdf_url")
        if pdf_url:
            attrs["pdf_url"] = pdf_url
        attrs["last_refresh_ok"] = self.coordinator.last_update_success
        attrs["utility"] = data.get("utility")
        attrs["provider"] = self.coordinator.provider
        return attrs


class FixedChargeSensor(BaseElectricSensor):
    """Monthly fixed customer charge in USD."""

    _attr_native_unit_of_measurement = "USD"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_fixed_charge"

    @property
    def name(self) -> str:
        return "Fixed customer charge"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        rs = _get_residential_standard(data)
        if not rs:
            return None
        val = rs.get("customer_charge_monthly_usd")
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None


class RatesLastRefreshSensor(BaseElectricSensor):
    """Timestamp of last refresh from backend."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_state_class = None

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_last_refresh"

    @property
    def name(self) -> str:
        return "Rates last refresh"

    @property
    def native_value(self) -> datetime | None:
        data = self.coordinator.data or {}
        fetched_at = data.get("fetched_at")
        if not fetched_at:
            return None
        try:
            dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None


class RatesAgeHoursSensor(BaseElectricSensor):
    """Age of rates in hours since last refresh."""

    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_age_hours"

    @property
    def name(self) -> str:
        return "Rates age"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        fetched_at = data.get("fetched_at")
        if not fetched_at:
            return None
        try:
            dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - dt
            return round(delta.total_seconds() / 3600.0, 2)
        except Exception:
            return None


class EnergyPriceSensor(BaseElectricSensor):
    """Primary cost entity for HA Energy Dashboard (USD/kWh)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_energy_price"

    @property
    def name(self) -> str:
        return "Energy price"

    @property
    def native_value(self) -> float | None:
        rs = _get_residential_standard(self.coordinator.data or {})
        if not rs:
            return None
        energy = float(rs.get("energy_rate_usd_per_kwh", 0))
        fuel = float(rs.get("tva_fuel_rate_usd_per_kwh", 0))
        return round(energy + fuel, 5)


class DailyFixedCostSensor(BaseElectricSensor):
    """Daily fixed cost estimate (USD/day)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = None

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_daily_fixed_cost"

    @property
    def name(self) -> str:
        return "Daily fixed cost"

    @property
    def native_value(self) -> float | None:
        rs = _get_residential_standard(self.coordinator.data or {})
        if not rs:
            return None
        monthly = float(rs.get("customer_charge_monthly_usd", 0))
        return round(monthly / 30.0, 5)


class MonthlyFixedCostSensor(BaseElectricSensor):
    """Monthly fixed customer charge (USD/month)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = None

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_monthly_fixed_cost"

    @property
    def name(self) -> str:
        return "Monthly fixed cost"

    @property
    def native_value(self) -> float | None:
        rs = _get_residential_standard(self.coordinator.data or {})
        if not rs:
            return None
        return float(rs.get("customer_charge_monthly_usd", 0))


# =============================================================================
# Water Sensors
# =============================================================================


class WaterUsageRateSensor(BaseWaterSensor):
    """Water usage rate in USD per gallon."""

    _attr_native_unit_of_measurement = "USD/gal"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_water_usage_rate"

    @property
    def name(self) -> str:
        return "Water usage rate"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        water = data.get("water") or {}
        use_rate = water.get("use_rate")
        if use_rate is None:
            return None
        try:
            return float(use_rate)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        water = data.get("water") or {}
        attrs: dict[str, object] = {
            "use_rate_unit": water.get("use_rate_unit"),
            "default_meter_size": water.get("default_meter_size"),
            "effective_date": water.get("effective_date"),
            "provider": self.coordinator.provider,
        }
        # Include meter sizes
        meter_sizes = water.get("meter_sizes")
        if meter_sizes:
            attrs["meter_sizes"] = meter_sizes
        return attrs


class WaterBaseChargeSensor(BaseWaterSensor):
    """Water base/service charge in USD."""

    _attr_native_unit_of_measurement = "USD"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_water_base_charge"

    @property
    def name(self) -> str:
        return "Water base charge"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        water = data.get("water") or {}
        base = water.get("base_charge")
        if base is None:
            return None
        try:
            return float(base)
        except (TypeError, ValueError):
            return None


class SewerUsageRateSensor(BaseWaterSensor):
    """Sewer usage rate in USD per gallon."""

    _attr_native_unit_of_measurement = "USD/gal"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_sewer_usage_rate"

    @property
    def name(self) -> str:
        return "Sewer usage rate"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        sewer = data.get("sewer")
        if not sewer:
            return None
        use_rate = sewer.get("use_rate")
        if use_rate is None:
            return None
        try:
            return float(use_rate)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        sewer = data.get("sewer") or {}
        return {
            "use_rate_unit": sewer.get("use_rate_unit"),
            "effective_date": sewer.get("effective_date"),
        }


class SewerBaseChargeSensor(BaseWaterSensor):
    """Sewer base/service charge in USD."""

    _attr_native_unit_of_measurement = "USD"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_sewer_base_charge"

    @property
    def name(self) -> str:
        return "Sewer base charge"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        sewer = data.get("sewer")
        if not sewer:
            return None
        base = sewer.get("base_charge")
        if base is None:
            return None
        try:
            return float(base)
        except (TypeError, ValueError):
            return None


class WaterRatesLastRefreshSensor(BaseWaterSensor):
    """Timestamp of last refresh from backend."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_state_class = None

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_water_last_refresh"

    @property
    def name(self) -> str:
        return "Rates last refresh"

    @property
    def native_value(self) -> datetime | None:
        data = self.coordinator.data or {}
        fetched_at = data.get("fetched_at")
        if not fetched_at:
            return None
        try:
            dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None


class WaterRatesAgeHoursSensor(BaseWaterSensor):
    """Age of rates in hours since last refresh."""

    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_water_age_hours"

    @property
    def name(self) -> str:
        return "Rates age"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        fetched_at = data.get("fetched_at")
        if not fetched_at:
            return None
        try:
            dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - dt
            return round(delta.total_seconds() / 3600.0, 2)
        except Exception:
            return None
