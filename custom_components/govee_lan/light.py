"""Govee LAN Control light platform - direct unicast UDP."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from homeassistant import core
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_DEVICE_IP,
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_MIN_COLOR_TEMP_KELVIN,
    CONF_MAX_COLOR_TEMP_KELVIN,
    GOVEE_CMD_PORT,
    GOVEE_SCAN_RESP_PORT,
    DEFAULT_POLL_INTERVAL,
    POLL_ATTEMPTS,
    POLL_TRY_TIMEOUT,
    MIN_COLOR_TEMP_KELVIN,
    MAX_COLOR_TEMP_KELVIN,
)
from .scenes import encode_scene, load_scene_catalog

_LOGGER = logging.getLogger(__name__)

_SCENE_CATALOG: dict[str, list[dict]] | None = None


async def _get_scenes_for_model(hass: core.HomeAssistant, model: str) -> list[dict]:
    global _SCENE_CATALOG
    if _SCENE_CATALOG is None:
        _SCENE_CATALOG = await hass.async_add_executor_job(load_scene_catalog)
    return _SCENE_CATALOG.get(model, [])


class GoveeProtocol(asyncio.DatagramProtocol):
    """Async UDP protocol for Govee device communication.

    The devices live on different subnets/VLANs from HA, so every exchange is
    routed *unicast*: HA sends from :4002 to device:4003, and the device replies
    unicast back to HA:4002 (from a random high source port — so we match
    replies by source IP, not port). Plain UDP has no retransmit, and a single
    dropped reply across the routed path would otherwise count as a timeout;
    send_and_receive retries a few times to absorb that loss (see flapping
    history). This protocol also rebuilds its socket on connection_lost so a
    transport that ever dies doesn't require a manual reload.
    """

    def __init__(self, hass: core.HomeAssistant) -> None:
        self._hass = hass
        self._transport: asyncio.DatagramTransport | None = None
        self._pending: dict[str, list[asyncio.Future]] = {}
        self._closing = False

    # -- lifecycle ---------------------------------------------------------
    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport

    def connection_lost(self, exc: Exception | None) -> None:
        # The shared socket died (interface flap, etc.). Without this handler
        # the dead transport stayed cached forever and only a reload fixed it.
        self._transport = None
        if self._closing:
            return
        _LOGGER.warning("Govee UDP socket lost (%s); reconnecting", exc)
        self._hass.async_create_task(self._reconnect())

    async def _reconnect(self) -> None:
        loop = asyncio.get_running_loop()
        delay = 2
        while not self._closing and self._transport is None:
            try:
                # Reuse this same protocol instance so existing light entities
                # keep working transparently once the new transport attaches.
                await loop.create_datagram_endpoint(
                    lambda: self,
                    local_addr=("0.0.0.0", GOVEE_SCAN_RESP_PORT),
                    reuse_port=True,
                )
                _LOGGER.info("Govee UDP socket reconnected")
                return
            except OSError as err:
                _LOGGER.debug("Govee reconnect failed (%s); retry in %ss", err, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    def close(self) -> None:
        self._closing = True
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    # -- io ----------------------------------------------------------------
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        # Match by source IP only: replies arrive from a random high port.
        ip = addr[0]
        pending = self._pending.get(ip)
        if not pending:
            return

        future = pending[0]
        if future.done():
            pending.pop(0)
            if not pending:
                self._pending.pop(ip, None)
            return

        try:
            future.set_result(json.loads(data.decode()))
        except (json.JSONDecodeError, asyncio.InvalidStateError):
            pass
        else:
            pending.pop(0)
            if not pending:
                self._pending.pop(ip, None)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("UDP error: %s", exc)

    def send_command(self, ip: str, cmd: str, data: dict) -> None:
        if self._transport is None:
            return
        msg = json.dumps({"msg": {"cmd": cmd, "data": data}}).encode()
        self._transport.sendto(msg, (ip, GOVEE_CMD_PORT))

    def send_raw(self, ip: str, msg: dict) -> None:
        if self._transport is None:
            return
        self._transport.sendto(json.dumps(msg).encode(), (ip, GOVEE_CMD_PORT))

    async def send_and_receive(
        self,
        ip: str,
        cmd: str,
        data: dict,
        attempts: int = POLL_ATTEMPTS,
        try_timeout: float = POLL_TRY_TIMEOUT,
    ) -> dict | None:
        """Send a request and await a reply, retransmitting on a lost datagram.

        Returns the first reply received across `attempts` tries, or None if all
        time out. Retransmission is what keeps a single dropped UDP reply on the
        routed cross-subnet path from flipping the device to unavailable.
        """
        if self._transport is None:
            return None
        loop = asyncio.get_running_loop()
        for _ in range(attempts):
            future: asyncio.Future[dict] = loop.create_future()
            self._pending.setdefault(ip, []).append(future)
            try:
                self.send_command(ip, cmd, data)
                return await asyncio.wait_for(future, timeout=try_timeout)
            except asyncio.TimeoutError:
                continue
            finally:
                pending = self._pending.get(ip)
                if pending is not None:
                    if future in pending:
                        pending.remove(future)
                    if not pending:
                        self._pending.pop(ip, None)
        return None


async def _get_protocol(hass: core.HomeAssistant) -> GoveeProtocol:
    """Get or create the shared GoveeProtocol instance."""
    existing = hass.data.get(DOMAIN, {}).get("protocol")
    if existing is not None:
        return existing

    loop = asyncio.get_running_loop()
    _, protocol = await loop.create_datagram_endpoint(
        lambda: GoveeProtocol(hass),
        local_addr=("0.0.0.0", GOVEE_SCAN_RESP_PORT),
        reuse_port=True,
    )
    hass.data.setdefault(DOMAIN, {})["protocol"] = protocol
    return protocol


async def async_setup_entry(
    hass: core.HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    ip = entry.data[CONF_DEVICE_IP]
    device_id = entry.data[CONF_DEVICE_ID]
    model = entry.data[CONF_DEVICE_MODEL]
    name = entry.data.get(CONF_DEVICE_NAME, f"Govee {model}")
    min_temp = entry.data.get(CONF_MIN_COLOR_TEMP_KELVIN, MIN_COLOR_TEMP_KELVIN)
    max_temp = entry.data.get(CONF_MAX_COLOR_TEMP_KELVIN, MAX_COLOR_TEMP_KELVIN)

    protocol = await _get_protocol(hass)
    scenes = await _get_scenes_for_model(hass, model)
    entity = GoveeLanLight(
        protocol,
        ip,
        device_id,
        model,
        name,
        entry.entry_id,
        scenes,
        min_temp,
        max_temp,
    )
    async_add_entities([entity])


class GoveeLanLight(LightEntity):
    _attr_has_entity_name = False
    _attr_min_color_temp_kelvin = MIN_COLOR_TEMP_KELVIN
    _attr_max_color_temp_kelvin = MAX_COLOR_TEMP_KELVIN
    _attr_supported_color_modes = {
        ColorMode.COLOR_TEMP,
        ColorMode.RGB,
    }

    def __init__(
        self,
        protocol: GoveeProtocol,
        ip: str,
        device_id: str,
        model: str,
        name: str,
        entry_id: str,
        scenes: list[dict],
        min_color_temp_kelvin: int = MIN_COLOR_TEMP_KELVIN,
        max_color_temp_kelvin: int = MAX_COLOR_TEMP_KELVIN,
    ) -> None:
        self._protocol = protocol
        self._ip = ip
        self._device_id = device_id
        self._model = model
        self._entry_id = entry_id
        self._last_poll: float = 0
        self._last_command: float = 0
        self._consecutive_timeouts = 0
        self._min_color_temp_kelvin = min_color_temp_kelvin
        self._max_color_temp_kelvin = max_color_temp_kelvin

        self._scenes = {s["name"]: s for s in scenes}

        ident = device_id.replace(":", "")
        self._attr_unique_id = f"govee_lan_{model}_{ident}"
        self._attr_name = name
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_rgb_color = (255, 255, 255)
        self._attr_color_temp_kelvin = 4000
        self._attr_color_mode = ColorMode.RGB
        self._attr_available = True
        self._attr_effect = None
        self._attr_min_color_temp_kelvin = min_color_temp_kelvin
        self._attr_max_color_temp_kelvin = max_color_temp_kelvin

        if scenes:
            self._attr_supported_features = LightEntityFeature.EFFECT
            self._attr_effect_list = sorted(self._scenes.keys())
        else:
            self._attr_supported_features = LightEntityFeature(0)
            self._attr_effect_list = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            manufacturer="Govee",
            model=self._model,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        effect_name = kwargs.get(ATTR_EFFECT)
        if effect_name is not None:
            scene = self._scenes.get(effect_name)
            if scene:
                packets = encode_scene(scene["code"], scene["param"])
                self._protocol.send_raw(
                    self._ip,
                    {"msg": {"cmd": "ptReal", "data": {"command": packets}}},
                )
                self._attr_effect = effect_name

        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            self._protocol.send_command(
                self._ip, "colorwc",
                {"color": {"r": r, "g": g, "b": b}, "colorTemInKelvin": 0},
            )
            self._attr_rgb_color = (r, g, b)
            self._attr_color_mode = ColorMode.RGB
            self._attr_effect = None

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = max(
                min(kwargs[ATTR_COLOR_TEMP_KELVIN], self._max_color_temp_kelvin),
                self._min_color_temp_kelvin,
            )
            self._protocol.send_command(
                self._ip, "colorwc",
                {"color": {"r": 0, "g": 0, "b": 0}, "colorTemInKelvin": kelvin},
            )
            self._attr_color_temp_kelvin = kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_effect = None

        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = max(min(int(kwargs[ATTR_BRIGHTNESS] * 100 / 255), 100), 1)
            self._protocol.send_command(
                self._ip, "brightness", {"value": brightness_pct},
            )
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        no_feature_kwargs = not any(
            k in kwargs for k in (ATTR_RGB_COLOR, ATTR_COLOR_TEMP_KELVIN, ATTR_BRIGHTNESS, ATTR_EFFECT)
        )
        if no_feature_kwargs:
            self._protocol.send_command(self._ip, "turn", {"value": 1})

        self._attr_is_on = True
        self._last_command = time.monotonic()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._protocol.send_command(self._ip, "turn", {"value": 0})
        self._attr_is_on = False
        self._attr_effect = None
        self._last_command = time.monotonic()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        now = time.monotonic()
        if self._last_poll and (now - self._last_poll) < DEFAULT_POLL_INTERVAL:
            return
        if self._last_command and (now - self._last_command) < 3:
            return
        self._last_poll = now

        resp = await self._protocol.send_and_receive(
            self._ip, "devStatus", {},
        )

        if resp is None:
            self._consecutive_timeouts += 1
            if self._consecutive_timeouts > 6:
                self._attr_available = False
            return

        self._consecutive_timeouts = 0
        self._attr_available = True

        data = resp.get("msg", {}).get("data", {})
        if not data:
            return

        on_off = data.get("onOff")
        if on_off is None:
            self._attr_is_on = False
        elif isinstance(on_off, bool):
            self._attr_is_on = on_off
        else:
            self._attr_is_on = int(on_off) == 1

        brightness_pct = data.get("brightness", 100)
        self._attr_brightness = max(min(int(255 * brightness_pct / 100), 255), 0)

        color = data.get("color", {})
        color_temp = data.get("colorTemInKelvin", 0)

        if color_temp and color_temp > 0:
            self._attr_color_temp_kelvin = color_temp
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif color:
            self._attr_rgb_color = (
                color.get("r", 255),
                color.get("g", 255),
                color.get("b", 255),
            )
            self._attr_color_mode = ColorMode.RGB
