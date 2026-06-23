"""Overall controller state: faults, rotary switches, summer mode, locks."""

from __future__ import annotations

from .component import (
    Component,
    coil,
    gauge,
    integer,
    operating_mode,
    raw_register,
    temperature,
)
from .utils import MonthDay


class Controller(Component):
    """Controller-wide status and settings."""

    error_status = integer(149, signed=False, doc="Error status register")
    max_flow_setpoint = temperature(98, doc="Maximum flow setpoint of the controller")
    switch_top = operating_mode(102, doc="Rotary switch RK1")
    switch_middle = operating_mode(103, doc="Rotary switch RK2")
    switch_bottom = operating_mode(104, doc="Rotary switch hot water")
    summer_outside_limit = temperature(
        116, writable=True, doc="Outside-temp threshold for summer mode"
    )
    outside_delay = gauge(
        117, 1.0, writable=True, unit="K/h", doc="Outside-temp adaptation delay"
    )
    frost_limit = temperature(122, writable=True, doc="Frost-protection threshold")
    station_address = integer(142, signed=False, doc="Modbus station address")
    summer_days_on = integer(114, writable=True, doc="Days to enter summer mode")
    summer_days_off = integer(115, writable=True, doc="Days to leave summer mode")

    collective_fault = coil(0, doc="Any fault present")
    summer_active = coil(8, doc="Summer mode active")
    auto_daylight_saving = coil(136, writable=True, doc="Auto summer/winter time")
    manual_levels_locked = coil(149, writable=True, doc="Manual override locked")
    rotary_switch_locked = coil(150, writable=True, doc="Rotary switch locked")

    _summer_start_raw = raw_register(112)
    _summer_end_raw = raw_register(113)

    @property
    def summer_start(self) -> MonthDay | None:
        """Start of the summer-mode window (day, month)."""
        raw = self._summer_start_raw
        return MonthDay(raw // 100, raw % 100) if raw else None

    @property
    def summer_end(self) -> MonthDay | None:
        """End of the summer-mode window (day, month)."""
        raw = self._summer_end_raw
        return MonthDay(raw // 100, raw % 100) if raw else None
