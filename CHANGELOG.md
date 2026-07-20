# Changelog

## 2.3.3 - 2026-07-20

- Rolled up 2.3.0-2.3.3 same-day maintenance updates into one release note for readability.
- Fixed options/configure UX by replacing menu-based flow with a single, labeled `Configure Govee Device` form.
- Added `Fetch scene catalog now` in configure options with SKU prefill, validation, and immediate fetch support.
- Ensured fetched scene catalogs are picked up on config-entry reload (no full Home Assistant restart needed).
- Unified icon/brand assets and aligned release documentation/metadata.

## 2.2.x maintenance rollup (2.2.1-2.2.7) - 2026-07-20

- Consolidated same-day 2.2.1-2.2.7 patch activity into one historical summary.
- Improved Home Assistant/HACS metadata and packaging reliability.
- Added and refined scene-catalog tooling (fetch/save flow, cleanup, duplicate-name handling).
- Added device color-temperature options and fixed a light platform import regression.
- Improved UDP discovery and overlapping-request handling for LAN reliability.
- Added local brand asset packaging support and documentation alignment.

## 2.2.0 - 2026-07-20

- Added HACS-compatible metadata and documentation updates.
- Added direct unicast UDP control for Govee LAN devices.
- Added local scene/effect support via ptReal.
- Added discovery and polling improvements for local network reliability.
- Added a validated color-temperature range for supported devices.
