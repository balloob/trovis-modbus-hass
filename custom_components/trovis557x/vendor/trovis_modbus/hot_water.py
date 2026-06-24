"""The domestic hot water circuit (HK4 / TW): setpoints and disinfection."""

from __future__ import annotations

import datetime

from modbus_connection.model import coil, enum, gauge, integer, raw_register

from .enums import OperatingMode, Weekday
from .model import TrovisComponent, temperature
from .utils import time_from_hhmm


class HotWater(TrovisComponent):
    """Domestic hot water: setpoints, charging and thermal disinfection."""

    storage_temperature = temperature(22)  # SF1
    storage_temperature_lower = temperature(23)  # SF2

    mode = enum(111, OperatingMode, writable=True, level_coil=94)
    setpoint_day = temperature(1799, writable=True)
    setpoint_active = temperature(1807)
    setpoint_max = temperature(1800, writable=True)
    setpoint_min = temperature(1801, writable=True)
    hysteresis = gauge(1802, 0.1, unit="K", writable=True)
    charge_overshoot = gauge(1803, 0.1, unit="K", writable=True)
    max_charge_temp = temperature(1805, writable=True)
    hold_value = temperature(1806, writable=True)  # minimum maintained temperature
    active_charge_setpoint = temperature(1837)
    return_max = temperature(1827, writable=True)
    disinfection_temp = temperature(1829, writable=True)
    disinfection_weekday = enum(1830, Weekday, writable=True)
    _disinfection_start_raw = raw_register(1831, writable=True)
    _disinfection_stop_raw = raw_register(1832, writable=True)
    disinfection_hold = integer(1838, writable=True, unit="min")  # hold duration

    automatic = coil(1799)  # following the time program
    disinfection_active = coil(1800)
    priority = coil(1801)  # hot water has priority over heating
    max_charge_limit_active = coil(1802)
    return_limit_active = coil(1803)
    standby = coil(1804)
    frost_protection = coil(1805)
    forced_charge = coil(1806, writable=True)
    solar_pump_running = coil(1807)
    manual_active = coil(7)
    charge_pump_running = coil(59, writable=True, level_coil=98)  # storage pump (SLP)
    circulation_pump_running = coil(60, writable=True, level_coil=99)  # ZP

    @property
    def disinfection_start(self) -> datetime.time | None:
        """Start time of the thermal-disinfection window."""
        return time_from_hhmm(self._disinfection_start_raw)

    @property
    def disinfection_stop(self) -> datetime.time | None:
        """End time of the thermal-disinfection window."""
        return time_from_hhmm(self._disinfection_stop_raw)

    async def set_setpoint(self, celsius: float) -> None:
        """Set the hot-water day setpoint (°C)."""
        await self.write("setpoint_day", celsius)

    async def set_mode(self, mode: OperatingMode) -> None:
        """Set the operating mode."""
        await self.write("mode", mode)

    async def start_forced_charge(self) -> None:
        """Trigger a one-off storage charge."""
        await self.write("forced_charge", True)
