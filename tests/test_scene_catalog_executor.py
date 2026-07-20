import asyncio
import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_FLOW_PATH = ROOT / "custom_components" / "govee_lan" / "config_flow.py"


class _Schema:
    def __init__(self, _schema: object) -> None:
        self.schema = _schema


def _identity(value: object, **kwargs: object) -> object:
    return value


homeassistant = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
homeassistant.core = core

config_entries_mod = types.ModuleType("homeassistant.config_entries")


class _BaseConfigFlow:
    def __init_subclass__(cls, **kwargs: object) -> None:
        return super().__init_subclass__()


class _BaseOptionsFlow:
    def async_create_entry(self, title: str, data: dict[str, object]) -> dict[str, object]:
        return {"title": title, "data": data}

    def async_show_form(self, **kwargs: object) -> dict[str, object]:
        return kwargs

    def async_abort(self, **kwargs: object) -> dict[str, object]:
        return kwargs


config_entries_mod.ConfigFlow = _BaseConfigFlow
config_entries_mod.OptionsFlow = _BaseOptionsFlow
config_entries_mod.ConfigEntry = object

data_entry_flow_mod = types.ModuleType("homeassistant.data_entry_flow")
data_entry_flow_mod.FlowResult = dict

vol_mod = types.ModuleType("voluptuous")
vol_mod.Schema = _Schema
vol_mod.Required = _identity
vol_mod.Optional = _identity

homeassistant.config_entries = config_entries_mod
homeassistant.data_entry_flow = data_entry_flow_mod

sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.config_entries"] = config_entries_mod
sys.modules["homeassistant.data_entry_flow"] = data_entry_flow_mod
sys.modules["voluptuous"] = vol_mod

package_name = "custom_components.govee_lan"
package = types.ModuleType(package_name)
package.__path__ = [str(ROOT / "custom_components" / "govee_lan")]
sys.modules[package_name] = package

spec = importlib.util.spec_from_file_location(f"{package_name}.config_flow", CONFIG_FLOW_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_scene_catalog_fetch_uses_executor() -> None:
    flow = module.GoveeLanOptionsFlow.__new__(module.GoveeLanOptionsFlow)
    flow.config_entry = types.SimpleNamespace(
        data={
            module.CONF_DEVICE_IP: "10.0.0.2",
            module.CONF_DEVICE_NAME: "Living Room",
            module.CONF_MIN_COLOR_TEMP_KELVIN: module.MIN_COLOR_TEMP_KELVIN,
            module.CONF_MAX_COLOR_TEMP_KELVIN: module.MAX_COLOR_TEMP_KELVIN,
            module.CONF_DEVICE_MODEL: "H702B",
            module.CONF_SKU: "H702B",
        },
        title="Living Room",
        entry_id="entry-1",
    )

    captured: dict[str, object] = {}

    async def async_add_executor_job(func, *args):
        captured["func"] = func
        captured["args"] = args
        return None

    def async_update_entry(entry, data, title):
        captured["updated_data"] = data
        captured["updated_title"] = title

    async def async_reload(entry_id):
        captured["reloaded_entry_id"] = entry_id

    flow.hass = types.SimpleNamespace(
        async_add_executor_job=async_add_executor_job,
        config_entries=types.SimpleNamespace(
            async_update_entry=async_update_entry,
            async_reload=async_reload,
        ),
    )

    result = asyncio.run(
        flow.async_step_init(
            {
                module.CONF_DEVICE_IP: "10.0.0.2",
                module.CONF_DEVICE_NAME: "Living Room",
                module.CONF_MIN_COLOR_TEMP_KELVIN: module.MIN_COLOR_TEMP_KELVIN,
                module.CONF_MAX_COLOR_TEMP_KELVIN: module.MAX_COLOR_TEMP_KELVIN,
                module.CONF_SKU: "H702B",
                module.CONF_FETCH_SCENE_CATALOG_NOW: True,
            }
        )
    )

    assert captured["func"] is module.fetch_and_save_scene_catalog
    assert captured["args"] == ("H702B",)
    assert captured["updated_title"] == "Living Room"
    assert captured["reloaded_entry_id"] == "entry-1"
    assert result == {"title": "", "data": {}}


def test_scene_catalog_fetch_requires_sku() -> None:
    flow = module.GoveeLanOptionsFlow.__new__(module.GoveeLanOptionsFlow)
    flow.config_entry = types.SimpleNamespace(
        data={
            module.CONF_DEVICE_IP: "10.0.0.2",
            module.CONF_DEVICE_NAME: "Living Room",
            module.CONF_MIN_COLOR_TEMP_KELVIN: module.MIN_COLOR_TEMP_KELVIN,
            module.CONF_MAX_COLOR_TEMP_KELVIN: module.MAX_COLOR_TEMP_KELVIN,
            module.CONF_DEVICE_MODEL: "H702B",
            module.CONF_SKU: "",
        },
        title="Living Room",
        entry_id="entry-1",
    )

    async def async_add_executor_job(func, *args):
        raise AssertionError("executor should not be called without a SKU")

    flow.hass = types.SimpleNamespace(
        async_add_executor_job=async_add_executor_job,
        config_entries=types.SimpleNamespace(
            async_update_entry=lambda *args, **kwargs: None,
            async_reload=lambda *args, **kwargs: None,
        ),
    )

    result = asyncio.run(
        flow.async_step_init(
            {
                module.CONF_DEVICE_IP: "10.0.0.2",
                module.CONF_DEVICE_NAME: "Living Room",
                module.CONF_MIN_COLOR_TEMP_KELVIN: module.MIN_COLOR_TEMP_KELVIN,
                module.CONF_MAX_COLOR_TEMP_KELVIN: module.MAX_COLOR_TEMP_KELVIN,
                module.CONF_SKU: "",
                module.CONF_FETCH_SCENE_CATALOG_NOW: True,
            }
        )
    )

    assert result["errors"] == {"base": "sku_required"}


def test_scene_catalog_fetch_failure_surfaces_error() -> None:
    flow = module.GoveeLanOptionsFlow.__new__(module.GoveeLanOptionsFlow)
    flow.config_entry = types.SimpleNamespace(
        data={
            module.CONF_DEVICE_IP: "10.0.0.2",
            module.CONF_DEVICE_NAME: "Living Room",
            module.CONF_MIN_COLOR_TEMP_KELVIN: module.MIN_COLOR_TEMP_KELVIN,
            module.CONF_MAX_COLOR_TEMP_KELVIN: module.MAX_COLOR_TEMP_KELVIN,
            module.CONF_DEVICE_MODEL: "H702B",
            module.CONF_SKU: "H702B",
        },
        title="Living Room",
        entry_id="entry-1",
    )

    async def async_add_executor_job(func, *args):
        raise OSError("network unreachable")

    flow.hass = types.SimpleNamespace(
        async_add_executor_job=async_add_executor_job,
        config_entries=types.SimpleNamespace(
            async_update_entry=lambda *args, **kwargs: None,
            async_reload=lambda *args, **kwargs: None,
        ),
    )

    result = asyncio.run(
        flow.async_step_init(
            {
                module.CONF_DEVICE_IP: "10.0.0.2",
                module.CONF_DEVICE_NAME: "Living Room",
                module.CONF_MIN_COLOR_TEMP_KELVIN: module.MIN_COLOR_TEMP_KELVIN,
                module.CONF_MAX_COLOR_TEMP_KELVIN: module.MAX_COLOR_TEMP_KELVIN,
                module.CONF_SKU: "H702B",
                module.CONF_FETCH_SCENE_CATALOG_NOW: True,
            }
        )
    )

    assert result["errors"] == {"base": "fetch_failed"}