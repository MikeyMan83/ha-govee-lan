"""Govee LAN Control - Direct unicast UDP control for Govee lights."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data.get(DOMAIN, {})
        data.pop(entry.entry_id, None)
        # Tear down the shared UDP protocol once the last device entry is gone
        # so a reload rebuilds the socket and rejoins the multicast group cleanly.
        remaining = [k for k in data if k != "protocol"]
        if not remaining:
            protocol = data.pop("protocol", None)
            if protocol is not None:
                protocol.close()
    return unload_ok
