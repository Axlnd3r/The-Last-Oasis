from __future__ import annotations

from typing import Any


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def apply_world_tick(tile: dict[str, Any], tick: int) -> None:
    degradation = float(tile["degradation"])
    resource = int(tile["resource"])
    hazard = float(tile["hazard"])

    degradation = clamp01(degradation + 0.006 + (tick % 7) * 0.0005)
    hazard = clamp01(hazard + 0.0015 * degradation)

    drain = int(1 + 3 * degradation)
    resource = max(0, resource - drain)
    if degradation < 0.25:
        resource = min(100, resource + 1)

    tile["degradation"] = degradation
    tile["resource"] = resource
    tile["hazard"] = hazard


def hazard_damage(hazard: float, degradation: float) -> int:
    x = hazard * (0.6 + degradation)
    if x < 0.15:
        return 0
    if x < 0.35:
        return 1
    if x < 0.65:
        return 2
    return 3

