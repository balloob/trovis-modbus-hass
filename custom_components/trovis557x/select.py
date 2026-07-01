"""Select entities for Trovis 557x."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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

from trovis_modbus.metadata import EnumMetadata

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity
from .metadata import require_enum_metadata


@dataclass(frozen=True, kw_only=True)
class TrovisSelectDescription(SelectEntityDescription):
    """Description of a Trovis select entity.

    Options come from trovis-modbus metadata. This description only selects
    the field and stores HA-specific presentation values.
    """

    component: str
    field: str
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

        enum_metadata = require_enum_metadata(self._subsystem, description.field)
        self._enum_metadata: EnumMetadata = enum_metadata

        self._option_by_key = {
            option.key: option for option in enum_metadata.options
        }
        self._key_by_value = {
            int(option.value): option.key for option in enum_metadata.options
        }

        self._attr_options = list(self._option_by_key)
        self._attr_entity_category = description.entity_category
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = getattr(self._subsystem, self.entity_description.field)
        if value is None:
            return None

        try:
            return self._key_by_value.get(int(value))
        except (TypeError, ValueError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        try:
            selected = self._option_by_key[option]
        except KeyError as err:
            raise HomeAssistantError(f"Unsupported TROVIS option: {option}") from err

        if not self.coordinator.device.writing_enabled:
            raise HomeAssistantError("Please enable writing for changes!")

        try:
            await self._subsystem.async_write_datapoint(
                self.entity_description.field,
                self._enum_metadata.enum_type(selected.value),
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