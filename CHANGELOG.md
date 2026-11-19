# Changelog

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
