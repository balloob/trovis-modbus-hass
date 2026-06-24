"""trovis-modbus — read a Samson Trovis 557x heating controller over Modbus.

Construct ``Trovis557x(unit)`` with a ``modbus_connection.ModbusUnit``, call
``await device.async_update()``, then read its sub-systems as normal Python
objects::

    device.sensors.outside_1
    device.heating_circuit_1.room_setpoint_active
    device.hot_water.charge_pump_running

The library is organized by sub-system — one file each for ``device_info``,
``controller``, ``clock``, ``sensors``, ``heating_circuit`` and ``hot_water`` —
built on the generic ``Component`` / ``RegisterField`` / ``CoilField`` framework
in ``modbus_connection.model``.
"""

from .clock import Clock
from .controller import Controller
from .device_info import DeviceInformation
from .enums import OperatingMode, Weekday
from .heating_circuit import HeatingCircuit
from .hot_water import HotWater
from .sensors import Sensors
from .trovis import Trovis557x
from .utils import OUTSIDE_TEMPERATURES, MonthDay, heating_curve

__all__ = [
    "OUTSIDE_TEMPERATURES",
    "Clock",
    "Controller",
    "DeviceInformation",
    "HeatingCircuit",
    "HotWater",
    "MonthDay",
    "OperatingMode",
    "Sensors",
    "Trovis557x",
    "Weekday",
    "heating_curve",
]
