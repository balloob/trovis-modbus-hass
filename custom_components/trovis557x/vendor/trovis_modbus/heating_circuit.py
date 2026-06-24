"""A space-heating circuit (RK1-3)."""

from __future__ import annotations

from modbus_connection.model import coil, enum, gauge, integer

from . import utils
from .enums import OperatingMode
from .model import TrovisComponent, temperature


class HeatingCircuit(TrovisComponent):
    """One space-heating circuit. Construct with ``index`` 1, 2 or 3.

    Addresses follow the controller's offset pattern: the 1000-block steps by
    200 per circuit, mode/control-signal by 2, pumps/manual status by 1.
    """

    # Measured temperatures, by the conventional per-circuit sensor wiring
    # (VF/RüF/RF input N feeds circuit N).
    flow_temperature = temperature(12, stride=1)  # VF
    return_temperature = temperature(16, stride=1)  # RüF
    room_temperature = temperature(19, stride=1)  # RF

    mode = enum(
        105, OperatingMode, stride=2, writable=True, level_coil=88, level_coil_stride=2
    )
    control_signal = integer(106, signed=False, stride=2, unit="%")  # valve position
    flow_setpoint = temperature(999, stride=200)
    flow_max = temperature(1000, stride=200, writable=True)
    flow_min = temperature(1001, stride=200, writable=True)
    room_setpoint_day = temperature(1002, stride=200, writable=True)
    room_setpoint_night = temperature(1003, stride=200, writable=True)
    room_setpoint_active = temperature(1004, stride=200)
    slope = gauge(1005, 0.1, stride=200, writable=True)  # heating-curve slope
    level = gauge(1006, 0.1, stride=200, writable=True, unit="K")  # heating-curve level
    return_slope = gauge(1008, 0.1, stride=200)  # return-curve slope
    return_level = gauge(1009, 0.1, stride=200, unit="K")  # return-curve level
    return_max = temperature(1010, stride=200, writable=True)
    return_base_point = temperature(1011, stride=200)  # return-curve foot point
    return_setpoint = temperature(1032, stride=200)
    flow_deviation = gauge(1062, 0.1, stride=200, unit="K")  # flow control deviation

    automatic = coil(999, stride=200)  # following the time program
    day_active = coil(1000, stride=200)
    night_active = coil(1001, stride=200)
    hold_active = coil(1002, stride=200)
    setback_active = coil(1003, stride=200)
    heat_up_active = coil(1004, stride=200)
    return_limit_active = coil(1005, stride=200)
    outside_shutdown = coil(1006, stride=200)
    standby = coil(1007, stride=200)
    frost_protection = coil(1008, stride=200)
    pump_running = coil(
        56, stride=1, writable=True, level_coil=95, level_coil_stride=1
    )  # circulation pump (UP)
    manual_active = coil(4, stride=1)

    def heating_curve(self, mode: str = "active") -> list[float] | None:
        """Flow-temperature curve over outside temps -20..20 °C.

        ``mode``: ``"active"`` (follow day/night state), ``"day"`` or ``"night"``.
        Returns ``None`` if a required value is missing; pair with
        :data:`utils.OUTSIDE_TEMPERATURES`.
        """
        if mode == "day" or (mode == "active" and self.day_active):
            room = self.room_setpoint_day
        else:
            room = self.room_setpoint_night
        slope, level = self.slope, self.level
        flow_min, flow_max = self.flow_min, self.flow_max
        if None in (room, slope, level, flow_min, flow_max):
            return None
        return utils.heating_curve(
            room_setpoint=room,  # type: ignore[arg-type]
            slope=slope,  # type: ignore[arg-type]
            level=level,  # type: ignore[arg-type]
            flow_min=flow_min,  # type: ignore[arg-type]
            flow_max=flow_max,  # type: ignore[arg-type]
        )

    async def set_mode(self, mode: OperatingMode) -> None:
        """Set the operating mode."""
        await self.write("mode", mode)

    async def set_room_setpoint_day(self, celsius: float) -> None:
        """Set the day room setpoint (°C)."""
        await self.write("room_setpoint_day", celsius)

    async def set_room_setpoint_night(self, celsius: float) -> None:
        """Set the night room setpoint (°C)."""
        await self.write("room_setpoint_night", celsius)
