"""Binary-sensor platform — diagnostic pump/fault/mode states."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity


@dataclass(frozen=True, kw_only=True)
class TrovisBinaryDescription(BinarySensorEntityDescription):
    """Describes a binary sensor reading one coil of one component."""

    component: str
    attribute: str


def _binary(
    component: str,
    attribute: str,
    name: str,
    device_class: BinarySensorDeviceClass | None = None,
    *,
    key: str | None = None,
    translation_key: str | None = None,
    translation_placeholders: dict[str, str] | None = None,
) -> TrovisBinaryDescription:
    return TrovisBinaryDescription(
        key=key or f"{component}_{attribute}",
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
        name=name,
        component=component,
        attribute=attribute,
        device_class=device_class,
        entity_category=EntityCategory.DIAGNOSTIC,
    )


_CONTROLLER: tuple[TrovisBinaryDescription, ...] = (
    _binary("controller", "general_fault", "Fault", BinarySensorDeviceClass.PROBLEM, key="general_fault"),
    _binary("controller", "summer_active", "Summer mode", key="summer_active"),
)

# Per-circuit coils (attribute, name, device_class).
_CIRCUIT: tuple[tuple[str, str, BinarySensorDeviceClass | None], ...] = (
    ("pump_running", "Pump", BinarySensorDeviceClass.RUNNING),
    ("frost_protection", "Frost protection", BinarySensorDeviceClass.COLD),
    ("standby", "Standby", None),
)

_HOT_WATER: tuple[TrovisBinaryDescription, ...] = (
    _binary(
        "hot_water",
        "charge_pump_running",
        "Charge pump",
        BinarySensorDeviceClass.HEAT,
        key="rk4dhw_charge_pump_running",
        translation_key="charge_pump_running",
        translation_placeholders={"rk": "Rk4"},
    ),
    _binary(
        "hot_water",
        "disinfection_active",
        "Disinfection",
        BinarySensorDeviceClass.RUNNING,
        key="rk4dhw_disinfection_active",
        translation_key="disinfection_active",
        translation_placeholders={"rk": "Rk4"},
    ),
    _binary(
        "hot_water",
        "circulation_pump_running",
        "Circulation pump",
        BinarySensorDeviceClass.RUNNING,
        key="rk4dhw_circulation_pump_running",
        translation_key="circulation_pump_running",
        translation_placeholders={"rk": "Rk4"},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trovis binary sensors."""
    coordinator = entry.runtime_data
    entities = [TrovisBinarySensor(coordinator, d) for d in (*_CONTROLLER, *_HOT_WATER)]
    for index in (1, 2, 3):
        component = f"heating_circuit_{index}"
        for attribute, name, device_class in _CIRCUIT:
            entities.append(
                TrovisBinarySensor(
                    coordinator,
                    _binary(
                        component,
                        attribute,
                        name,
                        device_class,
                        key=f"rk{index}_{attribute}",
                        translation_key=attribute,
                        translation_placeholders={"rk": f"Rk{index}"},
                    ),
                )
            )
    async_add_entities(entities)


class TrovisBinarySensor(TrovisEntity, BinarySensorEntity):
    """A single coil read from a component attribute."""

    entity_description: TrovisBinaryDescription

    def __init__(
        self, coordinator: TrovisCoordinator, description: TrovisBinaryDescription
    ) -> None:
        super().__init__(
            coordinator,
            description.key,
            description.component,
            "binary_sensor",
            translation_key=description.translation_key,
            translation_placeholders=description.translation_placeholders,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return getattr(self._subsystem, self.entity_description.attribute)
