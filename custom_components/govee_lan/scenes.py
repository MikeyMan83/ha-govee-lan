"""Govee scene encoding and catalog for LAN ptReal commands."""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


def _xor_checksum(data: bytes) -> int:
    result = 0
    for b in data:
        result ^= b
    return result & 0xFF


def _finish_packet(data: list[int]) -> bytes:
    while len(data) < 19:
        data.append(0x00)
    data = data[:19]
    data.append(_xor_checksum(bytes(data)))
    return bytes(data)


def encode_scene(scene_code: int, scence_param_b64: str) -> list[str]:
    """Encode a scene into base64 ptReal packets.

    Algorithm verified against govee2mqtt test vectors.
    """
    param_bytes = base64.b64decode(scence_param_b64)

    data = [0xA3, 0x00, 0x01, 0x00, 0x02]
    num_lines = 0
    last_line_marker = 1

    for b in param_bytes:
        if len(data) % 19 == 0:
            num_lines += 1
            data.append(0xA3)
            last_line_marker = len(data)
            data.append(num_lines)
        data.append(b)

    data[last_line_marker] = 0xFF
    data[3] = num_lines + 1

    padded = bytearray()
    for i in range(0, len(data), 19):
        chunk = list(data[i : i + 19])
        padded.extend(_finish_packet(chunk))

    lo = scene_code & 0xFF
    hi = (scene_code >> 8) & 0xFF
    padded.extend(_finish_packet([0x33, 0x05, 0x04, lo, hi]))

    return [
        base64.b64encode(bytes(padded[i : i + 20])).decode("ascii")
        for i in range(0, len(padded), 20)
    ]


def load_scene_catalog() -> dict[str, list[dict]]:
    """Load bundled scene catalogs keyed by SKU."""
    catalog_dir = Path(__file__).parent / "scene_data"
    result: dict[str, list[dict]] = {}
    if not catalog_dir.is_dir():
        return result
    for f in catalog_dir.glob("*.json"):
        sku = f.stem
        try:
            result[sku] = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            _LOGGER.warning("Failed to load scene catalog for %s", sku)
    return result
