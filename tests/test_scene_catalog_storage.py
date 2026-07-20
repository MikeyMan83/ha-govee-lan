import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENES_PATH = ROOT / "custom_components" / "govee_lan" / "scenes.py"


def _load_scenes_module():
    package_name = "custom_components.govee_lan"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(ROOT / "custom_components" / "govee_lan")]
        sys.modules[package_name] = package

    spec = importlib.util.spec_from_file_location(f"{package_name}.scenes", SCENES_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scene_catalog_save_and_load_round_trip(tmp_path, monkeypatch) -> None:
    scenes = _load_scenes_module()
    monkeypatch.setattr(scenes, "__file__", str(tmp_path / "scenes.py"))

    payload = [
        {"name": "Sunrise", "code": 101, "param": "abc", "category": "Color"},
        {"name": "Movie", "code": 202, "param": "def", "category": "Scene"},
    ]

    target = scenes.save_scene_catalog("H702B", payload)

    assert target == Path(tmp_path / "scene_data" / "H702B.json")
    assert scenes.load_scene_catalog() == {"H702B": payload}


def test_scene_catalog_loader_ignores_broken_json(tmp_path, monkeypatch) -> None:
    scenes = _load_scenes_module()
    monkeypatch.setattr(scenes, "__file__", str(tmp_path / "scenes.py"))

    catalog_dir = tmp_path / "scene_data"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "good.json").write_text('[{"name": "Good"}]', encoding="utf-8")
    (catalog_dir / "broken.json").write_text("{not valid json", encoding="utf-8")

    assert scenes.load_scene_catalog() == {"good": [{"name": "Good"}]}