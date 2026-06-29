"""Select entities for Trovis 557x."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ._local_dev import apply_local_trovis_modbus_override
apply_local_trovis_modbus_override()

from trovis_modbus.enums import OperatingMode
from trovis_modbus import (
    TrovisWriteAccessDisabledError,
    TrovisWriteAccessError,
    TrovisWriteNotImplementedError,
)

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity


OPTION_STANDBY = "standby"
OPTION_MANUAL = "manual"
OPTION_DAY = "day"
OPTION_NIGHT = "night"

OPERATION_MODE_OPTIONS: dict[str, OperatingMode] = {
    OPTION_STANDBY: OperatingMode.STANDBY,
    OPTION_MANUAL: OperatingMode.MANUAL,
    OPTION_DAY: OperatingMode.DAY,
    OPTION_NIGHT: OperatingMode.NIGHT,
}

OPERATION_MODE_BY_VALUE: dict[OperatingMode, str] = {
    value: option for option, value in OPERATION_MODE_OPTIONS.items()
}


@dataclass(frozen=True, kw_only=True)
class TrovisSelectDescription(SelectEntityDescription):
    """Description of a Trovis select entity."""

    component: str
    field: str
    options: list[str]
    translation_placeholders: dict[str, str] | None = None


def _operation_mode(
    component: str,
    key: str,
    placeholder: str,
) -> TrovisSelectDescription:
    """Return an operation-mode select description."""
    return TrovisSelectDescription(
        key=key,
        translation_key="operation_mode",
        name=f"{placeholder} operation mode",
        component=component,
        field="mode",
        options=list(OPERATION_MODE_OPTIONS),
        entity_category=EntityCategory.CONFIG,
        translation_placeholders={"rk": placeholder},
    )


_SELECTS: tuple[TrovisSelectDescription, ...] = (
    _operation_mode("heating_circuit_1", "rk1_operation_mode", "Rk1"),
    _operation_mode("heating_circuit_2", "rk2_operation_mode", "Rk2"),
    _operation_mode("heating_circuit_3", "rk3_operation_mode", "Rk3"),
    _operation_mode("hot_water", "rk4dhw_operation_mode", "Rk4"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trovis select entities."""
    coordinator = entry.runtime_data
    async_add_entities(TrovisSelect(coordinator, description) for description in _SELECTS)


class TrovisSelect(TrovisEntity, SelectEntity):
    """Trovis select entity."""

    entity_description: TrovisSelectDescription

    def __init__(
        self,
        coordinator: TrovisCoordinator,
        description: TrovisSelectDescription,
    ) -> None:
        super().__init__(
            coordinator,
            description.key,
            description.component,
            "select",
            translation_key=description.translation_key,
            translation_placeholders=description.translation_placeholders,
        )
        self.entity_description = description
        self._attr_options = description.options


    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = getattr(self._subsystem, self.entity_description.field)

        if value is None:
            return None

        try:
            mode = value if isinstance(value, OperatingMode) else OperatingMode(value)
        except ValueError:
            return None

        return OPERATION_MODE_BY_VALUE.get(mode)


    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option not in OPERATION_MODE_OPTIONS:
            raise HomeAssistantError(f"Unsupported TROVIS option: {option}")

        if not self.coordinator.device.writing_enabled:
            raise HomeAssistantError("Please enable writing for changes!")

        try:
            await self._subsystem.async_write_datapoint(
                self.entity_description.field,
                OPERATION_MODE_OPTIONS[option],
                access_code=self.coordinator.access_code,
            )
        except (TrovisWriteAccessDisabledError, TrovisWriteAccessError) as err:
            raise HomeAssistantError(str(err)) from err
        except TrovisWriteNotImplementedError as err:
            raise HomeAssistantError(
                "Writing TROVIS data points is not implemented yet"
            ) from err

        await self.coordinator.async_request_refresh()