"""
pipeline/zones.py
Zone assignment using ray-casting point-in-polygon.
Zones are per-camera: only zones owned by the given camera_id are checked.
"""
from __future__ import annotations

import os
from typing import Optional

import yaml

_config_cache: dict = {}


def _load_config(config_path: Optional[str] = None) -> dict:
    path = config_path or os.path.join(
        os.getenv("CONFIG_DIR", "config"), "store_ST1008.yaml"
    )
    if path not in _config_cache:
        with open(path) as f:
            _config_cache[path] = yaml.safe_load(f)
    return _config_cache[path]


def _point_in_polygon(x: float, y: float, polygon: list) -> bool:
    """Ray-casting algorithm."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def assign_zone(
    feet_point: tuple[float, float],
    camera_id: str,
    config: Optional[dict] = None,
    config_path: Optional[str] = None,
) -> Optional[str]:
    """
    Returns zone_id if feet_point falls inside a zone polygon owned by camera_id.
    Only zones whose 'camera' field matches camera_id are checked.
    """
    if config is None:
        config = _load_config(config_path)

    x, y = feet_point
    ownership = config.get("camera_zone_ownership", {})
    owned_zones = set(ownership.get(camera_id, []))

    for zone_id, zone_data in config.get("zones", {}).items():
        if zone_id not in owned_zones:
            continue
        polygon = zone_data.get("polygon", [])
        if polygon and _point_in_polygon(x, y, polygon):
            return zone_id
    return None


def camera_owns_zone(camera_id: str, zone_id: str, config: Optional[dict] = None) -> bool:
    if config is None:
        config = _load_config()
    ownership = config.get("camera_zone_ownership", {})
    return zone_id in ownership.get(camera_id, [])


def get_camera_role(camera_id: str, config: Optional[dict] = None) -> str:
    """Returns role string: product_zone | entry_exit | staff_only | billing"""
    if config is None:
        config = _load_config()
    return config.get("camera_roles", {}).get(camera_id, "product_zone")


def is_in_glass_mask(x: float, y: float, config: Optional[dict] = None) -> bool:
    """Returns True if point is inside a glass/mirror exclusion polygon."""
    if config is None:
        config = _load_config()
    for poly in config.get("glass_mask_polygons", []):
        if _point_in_polygon(x, y, poly):
            return True
    return False
