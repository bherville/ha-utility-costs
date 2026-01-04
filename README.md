# HA Utility Costs

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/bherville/ha-utility-costs.svg)](https://github.com/bherville/ha-utility-costs/releases)

A Home Assistant custom integration for tracking utility rates from [eRateManager](https://github.com/bherville/eratemanager).

## Features

- **Electric Rates**: Track energy rates, fuel costs, and fixed charges from supported electric providers
- **Water Rates**: Track water usage rates, base charges, and sewer rates from supported water providers
- **Energy Dashboard Compatible**: Sensors are compatible with Home Assistant's Energy Dashboard
- **Auto-refresh**: Rates are automatically refreshed from the eRateManager backend

## Supported Providers

### Electric Providers
- **CEMC** - Cumberland Electric Membership Corporation
- **NES** - Nashville Electric Service
- **KUB** - Knoxville Utilities Board

### Water Providers
- **WHUD** - White House Utility District

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add `https://github.com/bherville/ha-utility-costs` as an Integration
5. Search for "HA Utility Costs" and install
6. Restart Home Assistant

### Manual

1. Copy `custom_components/ha_utility_costs` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services → Add Integration
2. Search for "HA Utility Costs"
3. Enter the eRateManager API URL (default: `https://rates.bherville.com`)
4. (Optional) Enter an API Token if your eRateManager instance requires authentication
5. Select the utility type (Electric or Water)
6. Choose your provider

## Sensors

### Electric Sensors
| Sensor | Unit | Description |
|--------|------|-------------|
| Total energy rate | USD/kWh | Combined energy + fuel rate |
| Energy price | USD/kWh | For Energy Dashboard integration |
| Fixed customer charge | USD | Monthly fixed charge |
| Daily fixed cost | USD | Fixed charge / 30 |
| Monthly fixed cost | USD | Monthly fixed charge |
| Rates last refresh | timestamp | When rates were last fetched |
| Rates age | hours | Time since last refresh |

### Water Sensors
| Sensor | Unit | Description |
|--------|------|-------------|
| Water usage rate | USD/gal | Per-gallon water rate |
| Water base charge | USD | Monthly water base/service charge |
| Sewer usage rate | USD/gal | Per-gallon sewer rate |
| Sewer base charge | USD | Monthly sewer base charge |
| Rates last refresh | timestamp | When rates were last fetched |
| Rates age | hours | Time since last refresh |

## Requirements

This integration requires a running [eRateManager](https://github.com/bherville/eratemanager) backend instance.

## Migration from ha-energy-cost

If you previously used `ha-energy-cost`:

1. Remove the old integration from HACS
2. Install this new `ha-utility-costs` integration
3. Add your electric provider through the config flow
4. Update any automations/dashboards to use the new entity IDs

## License

MIT License - See [LICENSE](LICENSE) for details.
