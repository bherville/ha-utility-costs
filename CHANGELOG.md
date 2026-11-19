# Changelog

## 0.4.0

### Minor Changes

- 9efe784: Add native out-of-the-box cost tracking, combined water+sewer rate, health monitoring, and Blueprint support directly in the integration (no user YAML required):

  - Sync live `force_refresh` service, `OptionsFlowHandler` (`refresh_interval`), and `API status` diagnostic sensors into the repository.
  - Add `CombinedWaterSewerRateSensor` (`USD/gal`) to water provider entries.
  - Add optional `tracked_energy_entities` and `tracked_power_entities` selectors to the UI Configure (`OptionsFlow`) form to automatically create daily/monthly cost sensors and projected monthly burn-rate sensors for user-selected devices.
  - Add `binary_sensor` platform (`API problem` diagnostic sensor for disconnects and stale rates >48h).
  - Add an importable `rate_change_alert.yaml` automation Blueprint.

## 0.3.0

### Minor Changes

- b88d87d: Update endpoints and payload parsing for eRateManager v2 API (`/api/v2/electric-rates/...`, `/api/v2/water-rates/...`, `electric_rates` response key, and array provider lists).

## 0.2.1

### Patch Changes

- 33c057d: Migrate canonical repository to GitLab (`bherville/home-assistant/ha-utility-costs`) with automated GitHub mirroring for HACS

## 0.2.0

### Minor Changes

- c88cb20: feat: support API token authentication for eratemanager API
  feat: add searchable dropdown for providers in config flow
  fix: correct API endpoint paths and improve error handling

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-12-31

### Added

- Initial release
- Support for electric providers: CEMC, NES, KUB
- Support for water providers: WHUD
- Electric sensors: total energy rate, energy price, fixed charges, rates age
- Water sensors: water usage rate, water base charge, sewer usage rate, sewer base charge
- Two-step config flow (utility type → provider selection)
- HACS compatible
