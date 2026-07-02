"""Number entities for Trovis 557x."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import (
    TrovisWriteAccessDisabledError,
    TrovisWriteAccessError,
    TrovisWriteNotImplementedError,
)

try:
    from trovis_modbus import TrovisValueValidationError
except ImportError:  # pragma: no cover - compatibility while developing locally
    from trovis_modbus.exceptions import TrovisValueValidationError

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity
from .metadata import (
    ha_unit_from_number,
    number_device_class_from_number,
    require_number_metadata,
)


@dataclass(frozen=True, kw_only=True)
class TrovisNumberDescription(NumberEntityDescription):
    """Description of a Trovis number entity.

    TROVIS-specific value metadata such as min/max/step/unit comes from
    trovis-modbus. This description only keeps HA-specific presentation
    overrides and the selected field name.
    """

    component: str
    field: str
    translation_placeholders: dict[str, str] | None = None


_CONTROLLER: tuple[TrovisNumberDescription, ...] = (
    TrovisNumberDescription(
        key="year",
        translation_key="year",
        name="Controller year",
        component="clock",
        field="year",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
)


def _rk_number_descriptions(index: int) -> tuple[TrovisNumberDescription, ...]:
    """Return number descriptions for one regulation circuit."""
    component = f"heating_circuit_{index}"
    key_prefix = f"rk{index}"
    placeholders = {"rk": f"Rk{index}"}

    return (
        TrovisNumberDescription(
            key=f"{key_prefix}_room_setpoint_day",
            translation_key="room_setpoint_day",
            name=f"Rk{index} room setpoint day",
            component=component,
            field="room_setpoint_day",
            mode=NumberMode.BOX,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
            translation_placeholders=placeholders,
        ),
        TrovisNumberDescription(
            key=f"{key_prefix}_room_setpoint_night",
            translation_key="room_setpoint_night",
            name=f"Rk{index} room setpoint night",
            component=component,
            field="room_setpoint_night",
            mode=NumberMode.BOX,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
            translation_placeholders=placeholders,
        ),
        TrovisNumberDescription(
            key=f"{key_prefix}_slope",
            translation_key="slope",
            name=f"Rk{index} slope",
            component=component,
            field="slope",
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            translation_placeholders=placeholders,
        ),
        TrovisNumberDescription(
            key=f"{key_prefix}_level",
            translation_key="level",
            name=f"Rk{index} level",
            component=component,
            field="level",
            mode=NumberMode.BOX,
            native_unit_of_measurement=UnitOfTemperature.KELVIN,
            entity_category=EntityCategory.CONFIG,
            translation_placeholders=placeholders,
        ),
    )


_HOT_WATER: tuple[TrovisNumberDescription, ...] = (
    TrovisNumberDescription(
        key="rk4dhw_setpoint",
        translation_key="dhw_setpoint",
        name="Rk4 setpoint",
        component="hot_water",
        field="setpoint_day",
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        translation_placeholders={"rk": "Rk4"},
    ),
    TrovisNumberDescription(
        key="rk4dhw_hold_value",
        translation_key="dhw_hold_value",
        name="Rk4 hold value",
        component="hot_water",
        field="hold_value",
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        translation_placeholders={"rk": "Rk4"},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trovis number entities."""
    coordinator = entry.runtime_data

    entities: list[TrovisNumber] = [
        TrovisNumber(coordinator, description) for description in _CONTROLLER
    ]

    for index in coordinator.device.heating_circuit_indices:
        entities.extend(
            TrovisNumber(coordinator, description)
            for description in _rk_number_descriptions(index)
        )

    entities.extend(TrovisNumber(coordinator, description) for description in _HOT_WATER)

    async_add_entities(entities)


class TrovisNumber(TrovisEntity, NumberEntity):
    """Trovis number entity."""

    entity_description: TrovisNumberDescription

    def __init__(
        self,
        coordinator: TrovisCoordinator,
        description: TrovisNumberDescription,
    ) -> None:
        super().__init__(
            coordinator,
            description.key,
            description.component,
            "number",
            translation_key=description.translation_key,
            translation_placeholders=description.translation_placeholders,
        )
        self.entity_description = description

        number = require_number_metadata(self._subsystem, description.field)

        self._attr_native_min_value = number.min_value
        self._attr_native_max_value = number.max_value
        self._attr_native_step = number.step

        self._attr_native_unit_of_measurement = (
            description.native_unit_of_measurement or ha_unit_from_number(number)
        )
        self._attr_device_class = (
            description.device_class or number_device_class_from_number(number)
        )

        self._attr_mode = description.mode
        self._attr_entity_category = description.entity_category
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    @property
    def native_value(self) -> float | int | None:
        """Return the current value."""
        return getattr(self._subsystem, self.entity_description.field)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        if not self.coordinator.device.writing_enabled:
            raise HomeAssistantError("Please enable writing for changes!")

        try:
            await self._subsystem.async_write_datapoint(
                self.entity_description.field,
                value,
                access_code=self.coordinator.access_code,
            )
        except (
            TrovisWriteAccessDisabledError,
            TrovisWriteAccessError,
            TrovisValueValidationError,
        ) as err:
            raise HomeAssistantError(str(err)) from err
        except TrovisWriteNotImplementedError as err:
            raise HomeAssistantError(
                "Writing TROVIS data points is not implemented yet"
            ) from err

        await self.coordinator.async_request_refresh()