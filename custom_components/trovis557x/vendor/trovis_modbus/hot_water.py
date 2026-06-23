"""The domestic hot water circuit (HK4 / TW): setpoints and disinfection."""

from __future__ import annotations

from .component import (
    Component,
    coil,
    gauge,
    integer,
    operating_mode,
    temperature,
    time_value,
    weekday_value,
)
from .enums import OperatingMode


class HotWater(Component):
    """Domestic hot water: setpoints, charging and thermal disinfection."""

    storage_temperature = temperature(22, doc="Storage temperature (SF1)")
    storage_temperature_lower = temperature(23, doc="Lower storage temperature (SF2)")

    mode = operating_mode(111, writable=True, level_coil=94, doc="Operating mode")
    setpoint_day = temperature(1799, writable=True, doc="Hot-water setpoint (day)")
    setpoint_active = temperature(1807, doc="Currently active hot-water setpoint")
    setpoint_max = temperature(1800, writable=True, doc="Maximum settable setpoint")
    setpoint_min = temperature(1801, writable=True, doc="Minimum settable setpoint")
    hysteresis = gauge(1802, 0.1, unit="K", writable=True, doc="Switching hysteresis")
    charge_overshoot = gauge(
        1803, 0.1, unit="K", writable=True, doc="Charging temp overshoot"
    )
    max_charge_temp = temperature(1805, writable=True, doc="Maximum charge temp")
    hold_value = temperature(1806, writable=True, doc="Hold (minimum) temperature")
    active_charge_setpoint = temperature(1837, doc="Active charging setpoint")
    return_max = temperature(1827, writable=True, doc="Maximum return temperature")
    disinfection_temp = temperature(1829, writable=True, doc="Disinfection temperature")
    disinfection_weekday = weekday_value(
        1830, writable=True, doc="Disinfection weekday"
    )
    disinfection_start = time_value(1831, writable=True, doc="Disinfection start time")
    disinfection_stop = time_value(1832, writable=True, doc="Disinfection stop time")
    disinfection_hold = integer(
        1838, writable=True, unit="min", doc="Disinfection hold duration"
    )

    automatic = coil(1799, doc="Time-program controlled")
    disinfection_active = coil(1800, doc="Thermal disinfection running")
    priority = coil(1801, doc="Hot-water priority active")
    max_charge_limit_active = coil(1802, doc="Max charge-temp limiting active")
    return_limit_active = coil(1803, doc="Return-temp limiting active")
    standby = coil(1804, doc="Standby")
    frost_protection = coil(1805, doc="Frost protection active")
    forced_charge = coil(1806, writable=True, doc="Force a storage charge")
    solar_pump_running = coil(1807, doc="Solar circuit pump on")
    manual_active = coil(7, doc="Manual mode active")
    charge_pump_running = coil(
        59, writable=True, level_coil=98, doc="Storage charge pump on"
    )
    circulation_pump_running = coil(
        60, writable=True, level_coil=99, doc="Circulation pump on"
    )

    @property
    def charging(self) -> bool | None:
        """Whether the storage is currently being charged (charge pump on)."""
        return self.charge_pump_running

    async def set_setpoint(self, celsius: float) -> None:
        """Set the hot-water day setpoint (°C)."""
        await self.write("setpoint_day", celsius)

    async def set_mode(self, mode: OperatingMode) -> None:
        """Set the operating mode."""
        await self.write("mode", mode)

    async def start_forced_charge(self) -> None:
        """Trigger a one-off storage charge."""
        await self.write("forced_charge", True)
