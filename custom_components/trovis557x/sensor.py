"""Sensor platform — diagnostic readings (temperatures, status, valve position).

Setpoints live on the climate / water-heater entities; room and storage
temperatures are those entities' current temperature. What remains here is
diagnostic, and is routed to the controller or the per-circuit / hot-water
sub-device it belongs to.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import OperatingMode

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity

_MODE_OPTIONS = [mode.name.lower() for mode in OperatingMode]


@dataclass(frozen=True, kw_only=True)
class TrovisSensorDescription(SensorEntityDescription):
    """Describes a sensor reading one attribute of one component."""

    component: str
    attribute: str


def _temp(
    component: str,
    attribute: str,
    name: str,
    *,
    key: str | None = None,
    enabled: bool = True,
    unit: str = UnitOfTemperature.CELSIUS,
) -> TrovisSensorDescription:
    return TrovisSensorDescription(
        key=key or attribute,
        name=name,
        component=component,
        attribute=attribute,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=unit,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


def _switch(
    component: str,
    attribute: str,
    name: str,
    *,
    key: str | None = None,
) -> TrovisSensorDescription:
    return TrovisSensorDescription(
        key=key or attribute,
        name=name,
        component=component,
        attribute=attribute,
        device_class=SensorDeviceClass.ENUM,
        options=_MODE_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    )


_GLOBAL: tuple[TrovisSensorDescription, ...] = (
    _temp("sensors", "af1", "AF1 outside sensor 1", key="outside_temperature_1"),
    _temp("sensors", "af2", "AF2 outside sensor 2", key="outside_temperature_2"),

    _temp("sensors", "vf1", "VF1 flow sensor 1", key="flow_temperature_1"),
    _temp("sensors", "vf2", "VF2 flow sensor 2", key="flow_temperature_2"),
    _temp("sensors", "vf3", "VF3 flow sensor 3", key="flow_temperature_3"),
    _temp("sensors", "vf4", "VF4 flow sensor 4", key="flow_temperature_4"),

    _temp("sensors", "ruef1", "RüF1 return sensor 1", key="return_temperature_1"),
    _temp("sensors", "ruef2", "RüF2 return sensor 2", key="return_temperature_2"),
    _temp("sensors", "ruef3", "RüF3 return sensor 3", key="return_temperature_3"),

    _temp("sensors", "rf1", "RF1 room sensor 1", key="room_temperature_1"),
    _temp("sensors", "rf2", "RF2 room sensor 2", key="room_temperature_2"),
    _temp("sensors", "rf3", "RF3 room sensor 3", key="room_temperature_3"),

    _temp("sensors", "sf1", "SF1 hot water sensor 1", key="dhw_storage_temperature"),
    _temp(
        "sensors",
        "sf2",
        "SF2 hot water sensor 2",
        key="dhw_storage_temperature_lower",
    ),
    _temp(
        "sensors",
        "sf3_fg3",
        "SF3/FG3 hot water sensor / remote control 3",
        key="storage_remote_temperature",
    ),

    _temp(
        "sensors",
        "fg1",
        "FG1 remote control 1",
        key="remote_adjustment_1",
        unit=UnitOfTemperature.KELVIN,
    ),
    _temp(
        "sensors",
        "fg2",
        "FG2 remote control 2",
        key="remote_adjustment_2",
        unit=UnitOfTemperature.KELVIN,
    ),

    _temp("controller", "max_flow_setpoint", "Max flow setpoint", enabled=False),
    _switch("controller", "switch_top", "Switch top"),
    _switch("controller", "switch_middle", "Switch middle"),
    _switch("controller", "switch_bottom", "Switch bottom"),

    TrovisSensorDescription(
        key="error_status",
        name="Error status",
        component="controller",
        attribute="error_status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trovis sensors."""
    coordinator = entry.runtime_data
    entities = [TrovisSensor(coordinator, description) for description in _GLOBAL]

    for index in (1, 2, 3):
        component = f"heating_circuit_{index}"
        entities.append(
            TrovisSensor(
                coordinator,
                TrovisSensorDescription(
                    key=f"circuit{index}_valve_setpoint",
                    name=f"Circuit {index} valve setpoint",
                    component=component,
                    attribute="valve_setpoint",
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
            )
        )
    async_add_entities(entities)


class TrovisSensor(TrovisEntity, SensorEntity):
    """A single value read from a component attribute."""

    entity_description: TrovisSensorDescription

    def __init__(
        self, coordinator: TrovisCoordinator, description: TrovisSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key, description.component, "sensor")
        self.entity_description = description

    @property
    def native_value(self) -> object:
        value = getattr(self._subsystem, self.entity_description.attribute)
        if isinstance(value, IntEnum):
            return value.name.lower()
        return value
