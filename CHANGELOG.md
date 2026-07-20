# Changelog

## 2.3.0 - 2026-07-20

- Bumped the manifest version to 2.3.0 as a clean minor release for the accumulated non-breaking feature, packaging, and documentation changes.
- Added local Home Assistant brand assets under `custom_components/govee_lan/brand/` so recent Home Assistant versions can serve the integration icon through the brand API.
- Kept the README release status aligned with the shipped package contents.

## 2.2.7 - 2026-07-20

- Bumped the manifest version to 2.2.7 for the latest HACS/Home Assistant release.
- Added local Home Assistant brand assets under `custom_components/govee_lan/brand/` so recent Home Assistant versions can serve the integration icon through the brand API.
- Updated packaging notes and release documentation to reflect the current status of the integration.

## 2.2.5 - 2026-07-20

- Added release notes and clarified HACS/manual install guidance.
- Improved scene-catalog fetching and cleanup for empty payloads.
- Added duplicate-name warnings for fetched scene catalogs.

## 2.2.4 - 2026-07-20

- Bumped the manifest version for HACS updates.
- Fixed a light-platform import issue that prevented the integration from loading.

## 2.2.3 - 2026-07-20

- Added per-device min/max color-temperature configuration in options.
- Added a scene-catalog fetch flow for downloading scene data by SKU.
- Added helpers for fetching and saving scene catalogs.

## 2.2.2 - 2026-07-20

- Improved UDP discovery reliability for routed and cross-VLAN networks.
- Fixed pending-reply handling for overlapping UDP requests.
- Adjusted effect handling so color and brightness updates are not dropped.

## 2.2.1 - 2026-07-20

- Updated manifest and packaging metadata for Home Assistant/HACS recognition.
- Added repository hygiene updates for generated Python artifacts.

## 2.2.0 - 2026-07-20

- Added HACS-compatible metadata and documentation updates.
- Added direct unicast UDP control for Govee LAN devices.
- Added local scene/effect support via ptReal.
- Added discovery and polling improvements for local network reliability.
- Added a validated color-temperature range for supported devices.
