"""Overall controller state: faults, rotary switches, summer mode, locks."""

from __future__ import annotations

from modbus_connection.model import coil, enum, gauge, integer, raw_register

from .enums import OperatingMode
from .model import TrovisComponent, temperature
from .utils import MonthDay


class Controller(TrovisComponent):
    """Controller-wide status and settings."""

    error_status = integer(149, signed=False)
    max_flow_setpoint = temperature(98)
    # The three front-panel rotary switches, top to bottom (RK1 / RK2 / hot water).
    switch_top = enum(102, OperatingMode)
    switch_middle = enum(103, OperatingMode)
    switch_bottom = enum(104, OperatingMode)
    summer_outside_limit = temperature(116, writable=True)
    outside_delay = gauge(117, 0.1, writable=True, unit="K/h")  # AT adaptation rate
    frost_limit = temperature(122, writable=True)
    station_address = integer(142, signed=False)
    summer_days_on = integer(114, writable=True)  # days above limit to enter summer
    summer_days_off = integer(115, writable=True)  # days below limit to leave summer

    collective_fault = coil(0)
    summer_active = coil(8)
    auto_daylight_saving = coil(136, writable=True)
    manual_levels_locked = coil(149, writable=True)
    rotary_switch_locked = coil(150, writable=True)

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
