"""Config flow for Govee LAN Control."""
from __future__ import annotations

import asyncio
import json
import logging
import socket
import struct
import urllib.error
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_DEVICE_IP,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICE_ID,
    CONF_MIN_COLOR_TEMP_KELVIN,
    CONF_MAX_COLOR_TEMP_KELVIN,
    CONF_SKU,
    GOVEE_SCAN_PORT,
    GOVEE_SCAN_RESP_PORT,
    GOVEE_MULTICAST_ADDR,
    MIN_COLOR_TEMP_KELVIN,
    MAX_COLOR_TEMP_KELVIN,
)
from .scenes import fetch_scene_catalog, save_scene_catalog

_LOGGER = logging.getLogger(__name__)


async def _scan_for_devices(target_ip: str | None = None) -> list[dict]:
    """Scan for Govee devices via unicast or multicast."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _scan_sync, target_ip)


def _scan_sync(target_ip: str | None = None) -> list[dict]:
    """Send a scan request and collect replies.

    Retries a few times with a short per-try timeout, same rationale as the
    status poller in light.py: plain UDP has no retransmit, and a single
    dropped reply on a routed/cross-VLAN path would otherwise read as
    "no devices found" even though the device is fine.

    Also sets SO_REUSEPORT (where available) so this scan socket can bind
    to the same port the shared GoveeProtocol in light.py already holds
    once at least one device is configured. Without it, the bind falls back
    to a random ephemeral port -- and since Govee devices always reply to
    the fixed response port rather than back to the sender's port, that
    fallback socket would never receive anything.
    """
    msg = json.dumps(
        {"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}
    ).encode()

    devices = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    try:
        sock.bind(("0.0.0.0", GOVEE_SCAN_RESP_PORT))
    except OSError:
        sock.bind(("0.0.0.0", 0))

    try:
        mreq = struct.pack(
            "4sl",
            socket.inet_aton(GOVEE_MULTICAST_ADDR),
            socket.INADDR_ANY,
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    except OSError:
        pass

    sock.settimeout(1.0)
    seen = set()

    for _ in range(3):
        if target_ip:
            sock.sendto(msg, (target_ip, GOVEE_SCAN_PORT))
        else:
            sock.sendto(msg, (GOVEE_MULTICAST_ADDR, GOVEE_SCAN_PORT))
        try:
            while True:
                data, addr = sock.recvfrom(4096)
                resp = json.loads(data.decode())
                device_data = resp.get("msg", {}).get("data", {})
                device_id = device_data.get("device")
                if device_id and device_id not in seen:
                    seen.add(device_id)
                    devices.append({
                        CONF_DEVICE_IP: device_data.get("ip", addr[0]),
                        CONF_DEVICE_ID: device_id,
                        CONF_DEVICE_MODEL: device_data.get("sku", "unknown"),
                        CONF_DEVICE_NAME: f"Govee {device_data.get('sku', '')} {device_id[-5:]}",
                    })
        except socket.timeout:
            if devices:
                break
            continue

    sock.close()
    return devices


class GoveeLanOptionsFlow(config_entries.OptionsFlow):
    """Options flow for editing a Govee device's configuration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_data[CONF_DEVICE_IP] = user_input[CONF_DEVICE_IP]
            if user_input.get(CONF_DEVICE_NAME):
                new_data[CONF_DEVICE_NAME] = user_input[CONF_DEVICE_NAME]
            new_data[CONF_MIN_COLOR_TEMP_KELVIN] = user_input[CONF_MIN_COLOR_TEMP_KELVIN]
            new_data[CONF_MAX_COLOR_TEMP_KELVIN] = user_input[CONF_MAX_COLOR_TEMP_KELVIN]
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data, title=new_data.get(CONF_DEVICE_NAME, self.config_entry.title),
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        current_ip = self.config_entry.data.get(CONF_DEVICE_IP, "")
        current_name = self.config_entry.data.get(CONF_DEVICE_NAME, self.config_entry.title)
        current_min = self.config_entry.data.get(CONF_MIN_COLOR_TEMP_KELVIN, MIN_COLOR_TEMP_KELVIN)
        current_max = self.config_entry.data.get(CONF_MAX_COLOR_TEMP_KELVIN, MAX_COLOR_TEMP_KELVIN)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_IP, default=current_ip): str,
                vol.Optional(CONF_DEVICE_NAME, default=current_name): str,
                vol.Optional(CONF_MIN_COLOR_TEMP_KELVIN, default=current_min): int,
                vol.Optional(CONF_MAX_COLOR_TEMP_KELVIN, default=current_max): int,
            }),
        )

    async def async_step_scene_catalog(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            sku = user_input[CONF_SKU]
            try:
                scenes = fetch_scene_catalog(sku)
                save_scene_catalog(sku, scenes)
            except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as err:
                _LOGGER.exception("Failed to fetch scene catalog for SKU %s", sku)
                errors["base"] = "fetch_failed"
            else:
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="scene_catalog",
            data_schema=vol.Schema({
                vol.Required(CONF_SKU): str,
            }),
            errors=errors,
        )


class GoveeLanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> GoveeLanOptionsFlow:
        return GoveeLanOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            ip = user_input[CONF_DEVICE_IP]
            devices = await _scan_for_devices(ip)

            if devices:
                dev = devices[0]
                await self.async_set_unique_id(dev[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=dev[CONF_DEVICE_NAME],
                    data=dev,
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_IP): str,
            }),
            errors=errors,
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Scan the network for devices (alternative entry point)."""
        devices = await _scan_for_devices()
        if not devices:
            return self.async_abort(reason="no_devices_found")

        for dev in devices:
            await self.async_set_unique_id(dev[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=dev[CONF_DEVICE_NAME],
                data=dev,
            )

        return self.async_abort(reason="no_devices_found")
