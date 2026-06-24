"""The top-level Trovis557x device object."""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection.model import Component, ComponentGroup

from .clock import Clock
from .controller import Controller
from .device_info import DeviceInformation
from .heating_circuit import HeatingCircuit
from .hot_water import HotWater
from .sensors import Sensors

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit


class Trovis557x:
    """A Samson Trovis 557x heating controller reached through a ``ModbusUnit``.

    The device is a tree of independently-updatable sub-systems::

        trovis = Trovis557x(unit)
        await trovis.async_update()
        trovis.sensors.outside_1                 # °C
        trovis.heating_circuit_1.room_setpoint_active
        trovis.heating_circuit_1.pump_running    # bool
        trovis.hot_water.charge_pump_running
        trovis.info.model

    Each sub-system can also be refreshed on its own (``await
    trovis.hot_water.async_update()``) and exposes ``add_update_listener`` so a
    single Home Assistant entity can subscribe to just the part it shows.
    """

    def __init__(self, unit: ModbusUnit) -> None:
        self._unit = unit
        self.info = DeviceInformation(unit)
        self.controller = Controller(unit)
        self.clock = Clock(unit)
        self.sensors = Sensors(unit)
        self.heating_circuit_1 = HeatingCircuit(unit, index=1)
        self.heating_circuit_2 = HeatingCircuit(unit, index=2)
        self.heating_circuit_3 = HeatingCircuit(unit, index=3)
        self.hot_water = HotWater(unit)
        # One pooled-read group over every sub-system; it derives the readable
        # ranges from the components and caches its block plan after the first poll.
        self._group = ComponentGroup(unit, self.components)

    @property
    def heating_circuits(self) -> tuple[HeatingCircuit, HeatingCircuit, HeatingCircuit]:
        """The three space-heating circuits, in order."""
        return (
            self.heating_circuit_1,
            self.heating_circuit_2,
            self.heating_circuit_3,
        )

    @property
    def components(self) -> tuple[Component, ...]:
        """Every sub-system, for iteration."""
        return (
            self.info,
            self.controller,
            self.clock,
            self.sensors,
            *self.heating_circuits,
            self.hot_water,
        )

    async def async_update(self) -> None:
        """Refresh every sub-system in as few Modbus calls as possible.

        All sub-systems share one unit, so their register and coil reads are
        pooled into a single consolidated set of block reads — adjacent registers
        from different sub-systems are fetched together — rather than each
        component querying independently. Listeners then fire per sub-system.
        """
        await self._group.async_update()
