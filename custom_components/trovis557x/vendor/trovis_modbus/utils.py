"""Small helpers shared across sub-systems: the heating curve and value types."""

from __future__ import annotations

from datetime import time
from typing import NamedTuple

# Outside-temperature x-axis shared by every heating curve.
OUTSIDE_TEMPERATURES: list[int] = list(range(-20, 21))


def time_from_hhmm(raw: int | None) -> time | None:
    """Decode the controller's packed HHMM time (e.g. 1430 -> 14:30)."""
    if raw is None:
        return None
    hour, minute = divmod(raw, 100)
    return time(hour=hour, minute=minute) if hour < 24 and minute < 60 else None


class MonthDay(NamedTuple):
    """A recurring day-of-year without a year (e.g. a summer-mode boundary)."""

    day: int
    month: int


def heating_curve(
    *,
    room_setpoint: float,
    slope: float,
    level: float,
    flow_min: float,
    flow_max: float,
) -> list[float]:
    """Flow temperatures for outside temps -20..20 °C, clamped to [min, max].

    Reproduces the formula from the upstream ``heating_curves.yaml`` exactly,
    including its ``(x - 20)`` reference shift. Pair element ``i`` with
    :data:`OUTSIDE_TEMPERATURES`\\ ``[i]``.
    """
    curve: list[float] = []
    for outside in OUTSIDE_TEMPERATURES:
        shifted = outside - 20
        flow = (
            24
            + level
            + 2 * slope * (room_setpoint - 20)
            - (0.1 + 0.9 * slope) * (1.5 * shifted + 0.01 * (shifted * shifted))
        )
        curve.append(round(max(flow_min, min(flow_max, flow)), 2))
    return curve
