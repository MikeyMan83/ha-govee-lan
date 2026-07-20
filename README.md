# Govee LAN Direct

A Home Assistant custom integration for controlling Govee lights over the
local network, using direct unicast UDP -- no cloud dependency, no
multicast requirement, and no rate limits. Works across VLANs.

This is a fork of [Brian Miller's govee-lan-direct](https://gitlab.phospher.com/brianmiller/govee-lan-direct)
(MIT licensed), extended with:

- Local scene/effect support via the undocumented `ptReal` command (the
  original only exposed on/off, brightness, RGB, and color temperature)
- Discovery reliability fixes for cross-VLAN networks (see
  [Network requirements](#network-requirements) below)
- A confirmed, empirically-tested color temperature range rather than the
  device's advertised (but not necessarily accurate) spec range
- HACS Support
- Local brand assets for Home Assistant's custom-integration icon API

## Features

- On/off, brightness, RGB color, color temperature -- all via the official
  documented Govee LAN API
- Local scene/effect selection (Rainbow, Sunset, Halloween, seasonal and
  licensed scene packs, etc.) via the reverse-engineered `ptReal` protocol
  -- no cloud round-trip needed once the catalog is on disk
- Automatic reconnection if the UDP socket dies (interface flap, etc.)
- `local_polling` -- works with no internet connection at all, as long as
  Home Assistant and the light can reach each other

## Requirements

- A Govee device with **LAN Control** enabled in the Govee Home app
  (Settings for the device -> LAN Control -> on)
- Home Assistant and the Govee device able to reach each other over UDP on
  ports **4001-4003** (see below if they're on different VLANs/subnets)

## Current release status

- Current release: 2.3.2
- Includes local brand images in `custom_components/govee_lan/brand/` so Home Assistant 2026.3+ can serve the integration icon directly from the installed custom component.
- Includes the scene-catalog, UDP reliability, and color-temperature range improvements described below.
- Scene-catalog fetch is available directly in the integration options form with SKU prefill and a `Fetch scene catalog now` toggle.

If the integration still shows "icon not available" after upgrading, restart Home Assistant and hard-refresh the browser once so the frontend drops any cached placeholder image.

## Installation

### HACS (recommended)

1. HACS -> Integrations -> top-right menu -> Custom repositories
2. Add this repo's URL, category "Integration"
3. Install "Govee LAN Direct", then restart Home Assistant

### Manual / local checkout

If you are testing from a local checkout, or installing the integration without HACS,
copy the entire `custom_components/govee_lan/` directory (not just one file)
into your Home Assistant `config/custom_components/` directory on the Home
Assistant host, then restart Home Assistant.

## Adding a device

Settings -> Devices & Services -> Add Integration -> "Govee LAN Direct" ->
enter the device's IP address.

If discovery fails with "Cannot connect to device" but the device is
definitely reachable (e.g. you can control it via `ptReal`/`colorwc` UDP
commands manually), see [Network requirements](#network-requirements) below
before assuming the device itself is at fault.

## Network requirements

Govee devices reply to LAN commands on a **fixed** UDP port (4002),
regardless of which port the request came from. This has two consequences
this integration works around:

- **VLANs/routed networks**: plain UDP has no retransmission, and a single
  dropped packet on a routed cross-subnet path will otherwise read as
  "device unreachable" even though it's fine. Both the discovery scan and
  the status poller retry a few times before giving up.
- **Adding a second device while a first is already running**: Home
  Assistant's own light polling holds port 4002 with `SO_REUSEPORT` once
  any device is configured. The discovery flow used when adding further
  devices also sets `SO_REUSEPORT` so it can share that port rather than
  falling back to a random one that would never receive the device's
  reply.

If you run VLANs (Govee devices on an IoT VLAN, Home Assistant elsewhere),
make sure your firewall allows UDP 4001-4003 in both directions between the
two, not just the single port you might test manually with.

## Scenes / effects

Scene catalogs aren't bundled for every SKU -- Govee's scene data lives on
their servers, keyed by SKU, and there's no single catalog covering every
device. To add scenes for your model:

- From Home Assistant: open `Settings -> Devices & Services -> Govee LAN Direct -> Configure`, confirm the prefilled SKU, enable `Fetch scene catalog now`, and save.
- Or from a local checkout, fetch it yourself with the helper script below.

```powershell
.\scripts\fetch_scenes.ps1 -Sku H702B
```

(Linux/macOS: a `curl` + `jq` equivalent is trivial to write from the same
endpoint if you'd rather not use PowerShell -- see the script for the exact
request shape.)

This calls Govee's own `light-effect-libraries` endpoint directly -- **not**
your Home Assistant instance or your local network -- so it works from any
machine with internet access. Drop the resulting `<SKU>.json` into
`custom_components/govee_lan/scene_data/` and reload the integration; a
light entity whose model matches that filename will pick up the effect list
automatically.

Scene catalogs are not fetched automatically when a light initializes. The
integration only fetches them when you explicitly run the options-flow fetch
step or use the helper script. The light entity then loads the matching local
catalog during config-entry setup.

A handful of catalogs are bundled already in `scene_data/` from testing:
H6076, H706A, H702B, H7094.

### Known scene quirks

- A few entries per catalog are simple built-in modes (single/double-digit
  codes, no payload) rather than true `ptReal`-encoded scenes -- the fetch
  script filters these out automatically since `encode_scene()` can't do
  anything useful with them.
- Duplicate scene names within a catalog (Govee does ship these) will
  silently shadow each other in Home Assistant's effect list, since
  effects are keyed by name. The fetch script warns about this; rename one
  of each pair in the JSON if you want both selectable.
- The `ptReal` packet framing `encode_scene()` implements is the "standard"
  layout used by most SKUs, but not universally -- a handful of models are
  known to need a different prefix byte. If scenes appear in the list but
  do the wrong thing (or nothing) on the device, this is likely why; test
  one scene before assuming a whole new catalog works.

## Color temperature range

`MIN_COLOR_TEMP_KELVIN` / `MAX_COLOR_TEMP_KELVIN` in `const.py` are set to
**2700-6500K**, matching the range Govee's own app exposes -- not the wider
2000-9000K some of these devices advertise on their spec sheet.

This was a deliberate choice, not an oversight: on RGBICW hardware (RGB
emitters blended with a single warm-white LED, no separate cool-white
channel), color temperature outside the app's range was confirmed, via
direct device polling, to produce genuinely wrong output -- a hue shift
toward magenta/purple, not just a duller or less accurate color. The
device's onboard color-mixing math appears to only be valid within the
range Govee calibrated and tested in their own app; sending values outside
it isn't "pushing the hardware a bit further," it's asking the firmware to
extrapolate somewhere it was never validated.

**If you're using a different SKU**, don't assume this range is universal
-- verify it for your own device before trusting it, the same way we did
here: set a color temperature via Home Assistant, then poll `devStatus`
directly (see `scripts/` or just watch Developer Tools -> States after the
next poll cycle) to see what the device itself reports, and compare against
what it visually looks like.

## Not currently supported

- **Per-segment/individually-addressable LED control.** Some Govee RGBIC
  devices support setting different colors on different sections of the
  same strip, via an undocumented binary `ptReal` sub-protocol distinct
  from the scene encoding used here. This is real for at least some SKUs,
  but the packet format is not standardized across models, evidence on
  whether it even works locally (versus only through Govee's cloud) is
  mixed and device-dependent, and it hasn't been reverse-engineered for
  any SKU tested against this integration. Not implemented.

## Credits

Originally based on [Brian Miller's govee-lan-direct](https://gitlab.phospher.com/brianmiller/govee-lan-direct).
`ptReal` scene encoding informed by the community reverse-engineering work
in [egold555/Govee-Reverse-Engineering](https://github.com/egold555/Govee-Reverse-Engineering)
and [wez/govee2mqtt](https://github.com/wez/govee2mqtt).

## License

MIT -- see [LICENSE](LICENSE).
