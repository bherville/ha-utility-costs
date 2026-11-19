---
"ha-utility-costs": minor
---

Add native out-of-the-box cost tracking, combined water+sewer rate, health monitoring, and Blueprint support directly in the integration (no user YAML required):

- Sync live `force_refresh` service, `OptionsFlowHandler` (`refresh_interval`), and `API status` diagnostic sensors into the repository.
- Add `CombinedWaterSewerRateSensor` (`USD/gal`) to water provider entries.
- Add optional `tracked_energy_entities` and `tracked_power_entities` selectors to the UI Configure (`OptionsFlow`) form to automatically create daily/monthly cost sensors and projected monthly burn-rate sensors for user-selected devices.
- Add `binary_sensor` platform (`API problem` diagnostic sensor for disconnects and stale rates >48h).
- Add an importable `rate_change_alert.yaml` automation Blueprint.
