"""Sensor entities for HA Utility Costs."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_PROVIDER_TYPE,
    CONF_TRACKED_ENERGY_ENTITIES,
    CONF_TRACKED_POWER_ENTITIES,
    HOURS_PER_MONTH,
    PROVIDER_TYPE_ELECTRIC,
    PROVIDER_TYPE_WATER,
    API_STATUS_CONNECTED,
    API_STATUS_AUTH_FAILED,
    API_STATUS_UNREACHABLE,
    API_STATUS_RATE_LIMITED,
    API_STATUS_UNKNOWN,
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
    """Create electric rate sensors and optional tracked-device cost sensors."""
    entities: list[SensorEntity] = [
        EnergyRateSensor(coordinator, entry),
        FixedChargeSensor(coordinator, entry),
        RatesLastRefreshSensor(coordinator, entry),
        RatesAgeHoursSensor(coordinator, entry),
        EnergyPriceSensor(coordinator, entry),
        DailyFixedCostSensor(coordinator, entry),
        MonthlyFixedCostSensor(coordinator, entry),
        ApiStatusSensor(coordinator, entry),
    ]

    for entity_id in entry.options.get(CONF_TRACKED_ENERGY_ENTITIES, []):
        entities.append(TrackedEnergyCostSensor(coordinator, entry, entity_id, "daily"))
        entities.append(TrackedEnergyCostSensor(coordinator, entry, entity_id, "monthly"))

    power_entities = entry.options.get(CONF_TRACKED_POWER_ENTITIES, [])
    for entity_id in power_entities:
        entities.append(TrackedPowerProjectedCostSensor(coordinator, entry, entity_id))
    if power_entities:
        entities.append(TrackedTotalBurnRateSensor(coordinator, entry, power_entities))

    return entities


def _create_water_sensors(
    coordinator: WaterRatesCoordinator, entry: ConfigEntry
) -> list[SensorEntity]:
    """Create water rate sensors."""
    return [
        WaterUsageRateSensor(coordinator, entry),
        WaterBaseChargeSensor(coordinator, entry),
        SewerUsageRateSensor(coordinator, entry),
        SewerBaseChargeSensor(coordinator, entry),
        CombinedWaterSewerRateSensor(coordinator, entry),
        WaterRatesLastRefreshSensor(coordinator, entry),
        WaterRatesAgeHoursSensor(coordinator, entry),
        WaterApiStatusSensor(coordinator, entry),
    ]


def _get_residential_standard(data: dict) -> dict | None:
    """Extract residential_standard rates from electric data."""
    # API returns "electric_rates" not "rates"
    electric_rates = data.get("electric_rates") or {}
    rs = electric_rates.get("residential_standard") or {}
    # Check if we have actual rate data (is_present or has energy_rate)
    if not rs.get("is_present") and rs.get("energy_rate_usd_per_kwh") is None:
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


class CombinedWaterSewerRateSensor(BaseWaterSensor):
    """Combined water and sewer usage rate in USD per gallon."""

    _attr_native_unit_of_measurement = "USD/gal"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_combined_water_sewer_rate"

    @property
    def name(self) -> str:
        return "Combined water & sewer usage rate"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        water = data.get("water") or {}
        sewer = data.get("sewer") or {}
        water_rate = water.get("use_rate")
        if water_rate is None:
            return None
        try:
            total = float(water_rate) + float(sewer.get("use_rate") or 0.0)
            return round(total, 5)
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


# =============================================================================
# Diagnostic Sensors
# =============================================================================


class ApiStatusSensor(BaseElectricSensor):
    """Diagnostic sensor showing API connection status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_api_status"

    @property
    def name(self) -> str:
        return "API status"

    @property
    def native_value(self) -> str:
        return getattr(self.coordinator, "api_status", API_STATUS_UNKNOWN)

    @property
    def icon(self) -> str:
        """Return icon based on status."""
        status = self.native_value
        if status == API_STATUS_CONNECTED:
            return "mdi:check-network"
        if status == API_STATUS_AUTH_FAILED:
            return "mdi:key-alert"
        if status == API_STATUS_UNREACHABLE:
            return "mdi:network-off"
        if status == API_STATUS_RATE_LIMITED:
            return "mdi:speedometer-slow"
        return "mdi:help-network"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional diagnostic attributes."""
        attrs: dict[str, object] = {
            "last_update_success": self.coordinator.last_update_success,
            "provider": self.coordinator.provider,
            "api_url": self.coordinator.api_url,
        }
        error_msg = getattr(self.coordinator, "_last_error_message", None)
        if error_msg:
            attrs["last_error"] = error_msg
        return attrs

    @property
    def available(self) -> bool:
        """Always available to show status even when API is down."""
        return True


class WaterApiStatusSensor(BaseWaterSensor):
    """Diagnostic sensor showing water API connection status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_water_api_status"

    @property
    def name(self) -> str:
        return "API status"

    @property
    def native_value(self) -> str:
        return getattr(self.coordinator, "api_status", API_STATUS_UNKNOWN)

    @property
    def icon(self) -> str:
        """Return icon based on status."""
        status = self.native_value
        if status == API_STATUS_CONNECTED:
            return "mdi:check-network"
        if status == API_STATUS_AUTH_FAILED:
            return "mdi:key-alert"
        if status == API_STATUS_UNREACHABLE:
            return "mdi:network-off"
        if status == API_STATUS_RATE_LIMITED:
            return "mdi:speedometer-slow"
        return "mdi:help-network"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional diagnostic attributes."""
        attrs: dict[str, object] = {
            "last_update_success": self.coordinator.last_update_success,
            "provider": self.coordinator.provider,
            "api_url": self.coordinator.api_url,
        }
        error_msg = getattr(self.coordinator, "_last_error_message", None)
        if error_msg:
            attrs["last_error"] = error_msg
        return attrs

    @property
    def available(self) -> bool:
        """Always available to show status even when API is down."""
        return True


# =============================================================================
# Optional Tracked Device Cost & Burn-Rate Sensors
# =============================================================================


def _current_energy_rate(coordinator: ElectricRatesCoordinator) -> float | None:
    """Return total residential energy rate (USD/kWh) if available."""
    rs = _get_residential_standard(coordinator.data or {})
    if not rs:
        return None
    try:
        return float(rs.get("energy_rate_usd_per_kwh") or 0.0) + float(
            rs.get("tva_fuel_rate_usd_per_kwh") or 0.0
        )
    except (TypeError, ValueError):
        return None


def _entity_label(hass: HomeAssistant | None, entity_id: str) -> str:
    """Resolve a human-friendly name for a tracked source entity."""
    if hass is not None:
        state = hass.states.get(entity_id)
        if state and state.attributes.get("friendly_name"):
            return str(state.attributes["friendly_name"])
    slug = entity_id.split(".", 1)[-1].replace("_", " ").strip()
    return slug.title()


def _read_kwh(state) -> float | None:
    """Convert an energy sensor state into kWh."""
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, "", "None"):
        return None
    try:
        val = float(state.state)
    except (TypeError, ValueError):
        return None
    unit = state.attributes.get("unit_of_measurement")
    if unit == "Wh":
        return val / 1000.0
    if unit == "MWh":
        return val * 1000.0
    return val


def _read_watts(state) -> float | None:
    """Convert a power sensor state into Watts."""
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, "", "None"):
        return None
    try:
        val = float(state.state)
    except (TypeError, ValueError):
        return None
    unit = state.attributes.get("unit_of_measurement")
    if unit == "kW":
        return val * 1000.0
    return val


def _period_key(period: str) -> str:
    """Return current local day or month key for resetting accumulators."""
    now = dt_util.now()
    if period == "daily":
        return now.strftime("%Y-%m-%d")
    return now.strftime("%Y-%m")


class TrackedEnergyCostSensor(BaseElectricSensor, RestoreSensor):
    """Tracks daily or monthly USD cost for a user-selected energy (kWh) entity."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:currency-usd"

    def __init__(
        self,
        coordinator: ElectricRatesCoordinator,
        entry: ConfigEntry,
        source_entity_id: str,
        period: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._source_entity_id = source_entity_id
        self._period = period
        self._kwh_used: float = 0.0
        self._last_meter_kwh: float | None = None
        self._period_key: str = _period_key(period)

    @property
    def unique_id(self) -> str:
        safe_src = self._source_entity_id.replace(".", "_")
        return f"{self._entry.entry_id}_{self._provider_key}_{safe_src}_{self._period}_cost"

    @property
    def name(self) -> str:
        label = _entity_label(self.hass, self._source_entity_id)
        suffix = "Cost Today" if self._period == "daily" else "Cost This Month"
        return f"{label} {suffix}"

    @property
    def available(self) -> bool:
        return super().available and self._current_cost() is not None

    def _current_cost(self) -> float | None:
        rate = _current_energy_rate(self.coordinator)
        if rate is None:
            return None
        return round(self._kwh_used * rate, 2)

    @property
    def native_value(self) -> float | None:
        return self._current_cost()

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "source_entity": self._source_entity_id,
            "period": self._period,
            "period_key": self._period_key,
            "kwh_used": round(self._kwh_used, 4),
            "last_meter_kwh": self._last_meter_kwh,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        current_key = _period_key(self._period)
        if last_state and last_state.attributes.get("period_key") == current_key:
            try:
                self._kwh_used = float(last_state.attributes.get("kwh_used") or 0.0)
            except (TypeError, ValueError):
                self._kwh_used = 0.0
            last_meter = last_state.attributes.get("last_meter_kwh")
            if last_meter is not None:
                try:
                    self._last_meter_kwh = float(last_meter)
                except (TypeError, ValueError):
                    self._last_meter_kwh = None
        if self._last_meter_kwh is None:
            self._last_meter_kwh = _read_kwh(self.hass.states.get(self._source_entity_id))

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source_entity_id], self._handle_source_change
            )
        )

    @callback
    def _handle_source_change(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        new_kwh = _read_kwh(new_state)
        if new_kwh is None:
            return

        current_key = _period_key(self._period)
        if current_key != self._period_key:
            self._period_key = current_key
            self._kwh_used = 0.0
            self._last_meter_kwh = new_kwh
        elif self._last_meter_kwh is None:
            self._last_meter_kwh = new_kwh
        else:
            delta = new_kwh - self._last_meter_kwh
            if delta > 0:
                self._kwh_used += delta
            self._last_meter_kwh = new_kwh

        self.async_write_ha_state()


class TrackedPowerProjectedCostSensor(BaseElectricSensor):
    """Projected monthly USD burn rate from a user-selected power (W/kW) entity."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-line"

    def __init__(
        self,
        coordinator: ElectricRatesCoordinator,
        entry: ConfigEntry,
        source_entity_id: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._source_entity_id = source_entity_id

    @property
    def unique_id(self) -> str:
        safe_src = self._source_entity_id.replace(".", "_")
        return f"{self._entry.entry_id}_{self._provider_key}_{safe_src}_projected_monthly_cost"

    @property
    def name(self) -> str:
        label = _entity_label(self.hass, self._source_entity_id)
        return f"{label} Projected Monthly Cost"

    @property
    def native_value(self) -> float | None:
        rate = _current_energy_rate(self.coordinator)
        watts = _read_watts(self.hass.states.get(self._source_entity_id) if self.hass else None)
        if rate is None or watts is None:
            return None
        return round((watts / 1000.0) * rate * HOURS_PER_MONTH, 2)

    @property
    def extra_state_attributes(self) -> dict:
        watts = _read_watts(self.hass.states.get(self._source_entity_id) if self.hass else None)
        return {
            "source_entity": self._source_entity_id,
            "current_watts": watts,
            "hours_per_month": HOURS_PER_MONTH,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source_entity_id], self._handle_power_change
            )
        )

    @callback
    def _handle_power_change(self, _event: Event) -> None:
        self.async_write_ha_state()


class TrackedTotalBurnRateSensor(BaseElectricSensor):
    """Combined projected monthly USD burn rate across all tracked power entities."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(
        self,
        coordinator: ElectricRatesCoordinator,
        entry: ConfigEntry,
        source_entity_ids: list[str],
    ) -> None:
        super().__init__(coordinator, entry)
        self._source_entity_ids = list(source_entity_ids)

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._provider_key}_tracked_total_projected_monthly_cost"

    @property
    def name(self) -> str:
        return "Tracked devices projected monthly cost"

    @property
    def native_value(self) -> float | None:
        rate = _current_energy_rate(self.coordinator)
        if rate is None or not self.hass:
            return None
        total_watts = 0.0
        for entity_id in self._source_entity_ids:
            watts = _read_watts(self.hass.states.get(entity_id))
            if watts is not None:
                total_watts += watts
        return round((total_watts / 1000.0) * rate * HOURS_PER_MONTH, 2)

    @property
    def extra_state_attributes(self) -> dict:
        return {"source_entities": self._source_entity_ids}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._source_entity_ids, self._handle_power_change
            )
        )

    @callback
    def _handle_power_change(self, _event: Event) -> None:
        self.async_write_ha_state()
