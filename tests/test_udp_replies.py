import asyncio
import importlib
import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

homeassistant = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
homeassistant.core = core
components = types.ModuleType("homeassistant.components")
light_mod = types.ModuleType("homeassistant.components.light")
class _DummyFeature(int):
    pass
light_mod.ATTR_BRIGHTNESS = "brightness"
light_mod.ATTR_COLOR_TEMP_KELVIN = "color_temp_kelvin"
light_mod.ATTR_EFFECT = "effect"
light_mod.ATTR_RGB_COLOR = "rgb_color"
light_mod.ColorMode = types.SimpleNamespace(COLOR_TEMP="color_temp", RGB="rgb")
light_mod.LightEntity = object
light_mod.LightEntityFeature = _DummyFeature
components.light = light_mod
config_entries_mod = types.ModuleType("homeassistant.config_entries")
config_entries_mod.ConfigEntry = object
config_entries_mod.OptionsFlow = object
helpers = types.ModuleType("homeassistant.helpers")
entity_mod = types.ModuleType("homeassistant.helpers.entity")
entity_mod.DeviceInfo = dict
entity_platform_mod = types.ModuleType("homeassistant.helpers.entity_platform")
entity_platform_mod.AddEntitiesCallback = object
helpers.entity = entity_mod
helpers.entity_platform = entity_platform_mod
homeassistant.components = components
homeassistant.config_entries = config_entries_mod
homeassistant.helpers = helpers
sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.components"] = components
sys.modules["homeassistant.components.light"] = light_mod
sys.modules["homeassistant.config_entries"] = config_entries_mod
sys.modules["homeassistant.helpers"] = helpers
sys.modules["homeassistant.helpers.entity"] = entity_mod
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform_mod

module = importlib.import_module("custom_components.govee_lan.light")


def test_pending_future_matching_is_per_request() -> None:
    protocol = module.GoveeProtocol.__new__(module.GoveeProtocol)
    protocol._pending = {}
    protocol._closing = False
    protocol._transport = None

    loop = asyncio.new_event_loop()
    try:
        future_a = loop.create_future()
        future_b = loop.create_future()
        protocol._pending["10.0.0.1"] = [future_a, future_b]

        packet = json.dumps({"msg": {"data": {"ok": True}}}).encode()
        protocol.datagram_received(packet, ("10.0.0.1", 1234))

        assert future_a.done() is True
        assert future_b.done() is False
        assert future_a.result() == {"msg": {"data": {"ok": True}}}
    finally:
        loop.close()
