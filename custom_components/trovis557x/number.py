"""Number entities for Trovis 557x."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory

from ._local_dev import apply_local_trovis_modbus_override
apply_local_trovis_modbus_override()

from trovis_modbus import (
    TrovisWriteAccessDisabledError,
    TrovisWriteAccessError,
    TrovisWriteNotImplementedError,
)
from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity


@dataclass(frozen=True, kw_only=True)
class TrovisNumberDescription(NumberEntityDescription):
    """Description of a Trovis number entity."""

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
        native_min_value=2000,
        native_max_value=2099,
        native_step=1,
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
            native_step=0.1,
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
            native_step=0.1,
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
            native_min_value=0.2,
            native_max_value=3.2,
            native_step=0.1,
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
            native_min_value=-30,
            native_max_value=30,
            native_step=0.1,
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
        native_step=0.1,
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
        native_step=0.1,
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

    for index in (1, 2, 3):
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
        except (TrovisWriteAccessDisabledError, TrovisWriteAccessError) as err:
            raise HomeAssistantError(str(err)) from err
        except TrovisWriteNotImplementedError as err:
            raise HomeAssistantError(
                "Writing TROVIS data points is not implemented yet"
            ) from err

        await self.coordinator.async_request_refresh()
