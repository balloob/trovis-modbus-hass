"""Switch entities for Trovis 557x."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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

from trovis_modbus.metadata import BooleanMetadata

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity
from .metadata import require_boolean_metadata

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TrovisSwitchDescription(SwitchEntityDescription):
    """Description of a Trovis switch entity.

    Boolean semantics come from trovis-modbus. This description only selects
    the field and stores HA-specific presentation values.
    """

    component: str
    field: str
    translation_placeholders: dict[str, str] | None = None


_CONTROLLER: tuple[TrovisSwitchDescription, ...] = (
    TrovisSwitchDescription(
        key="delayed_outside_temp_adjustment_falling",
        translation_key="delayed_outside_temp_adjustment_falling",
        name="Delayed outside-temperature adjustment falling",
        component="controller",
        field="delayed_outside_temp_adjustment_falling",
        entity_category=EntityCategory.CONFIG,
    ),
    TrovisSwitchDescription(
        key="delayed_outside_temp_adjustment_rising",
        translation_key="delayed_outside_temp_adjustment_rising",
        name="Delayed outside-temperature adjustment rising",
        component="controller",
        field="delayed_outside_temp_adjustment_rising",
        entity_category=EntityCategory.CONFIG,
    ),
    TrovisSwitchDescription(
        key="automatic_daylight_saving_time",
        translation_key="automatic_daylight_saving_time",
        name="Automatic daylight-saving time",
        component="controller",
        field="auto_daylight_saving",
        entity_category=EntityCategory.CONFIG,
    ),
)


def _rk_switch_descriptions(index: int) -> tuple[TrovisSwitchDescription, ...]:
    """Return switch descriptions for one regulation circuit."""
    component = f"heating_circuit_{index}"
    key_prefix = f"rk{index}"
    placeholders = {"rk": f"Rk{index}"}

    return (
        TrovisSwitchDescription(
            key=f"{key_prefix}_optimization",
            translation_key="optimization",
            name=f"Rk{index} optimization",
            component=component,
            field="optimization",
            entity_category=EntityCategory.CONFIG,
            translation_placeholders=placeholders,
        ),
        TrovisSwitchDescription(
            key=f"{key_prefix}_adaptation",
            translation_key="adaptation",
            name=f"Rk{index} adaptation",
            component=component,
            field="adaptation",
            entity_category=EntityCategory.CONFIG,
            translation_placeholders=placeholders,
        ),
        TrovisSwitchDescription(
            key=f"{key_prefix}_room_control_unit",
            translation_key="room_control_unit",
            name=f"Rk{index} room control unit",
            component=component,
            field="room_control_unit",
            entity_category=EntityCategory.CONFIG,
            translation_placeholders=placeholders,
        ),
    )


_HOT_WATER: tuple[TrovisSwitchDescription, ...] = (
    TrovisSwitchDescription(
        key="rk4dhw_intermediate_heating_operation",
        translation_key="intermediate_heating_operation",
        name="Rk4 intermediate heating operation",
        component="hot_water",
        field="intermediate_heating_operation",
        entity_category=EntityCategory.CONFIG,
        translation_placeholders={"rk": "Rk4"},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trovis switch entities."""
    coordinator = entry.runtime_data

    entities: list[SwitchEntity] = [TrovisWriteAccessSwitch(coordinator)]

    entities.extend(
        TrovisSwitch(coordinator, description) for description in _CONTROLLER
    )

    for index in coordinator.device.heating_circuit_indices:
        entities.extend(
            TrovisSwitch(coordinator, description)
            for description in _rk_switch_descriptions(index)
        )

    entities.extend(TrovisSwitch(coordinator, description) for description in _HOT_WATER)

    async_add_entities(entities)


class TrovisWriteAccessSwitch(TrovisEntity, SwitchEntity):
    """Root switch that enables or disables TROVIS write access."""

    _attr_icon = "mdi:pencil-lock"

    def __init__(self, coordinator: TrovisCoordinator) -> None:
        super().__init__(
            coordinator,
            "write_access",
            "controller",
            "switch",
            translation_key="write_access",
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether TROVIS writing is enabled."""
        return self.coordinator.device.writing_enabled

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable TROVIS writing."""
        try:
            await self.coordinator.device.async_enable_writing(
                access_code=self.coordinator.access_code,
            )
        except TrovisWriteAccessError as err:
            raise HomeAssistantError(str(err)) from err

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable TROVIS writing."""
        try:
            await self.coordinator.device.async_disable_writing()
        except TrovisWriteAccessError as err:
            _LOGGER.debug(
                "Controller rejected resetting TROVIS write access; "
                "disabling the HA write gate only",
                exc_info=err,
            )

        await self.coordinator.async_request_refresh()


class TrovisSwitch(TrovisEntity, SwitchEntity):
    """Trovis switch entity."""

    entity_description: TrovisSwitchDescription

    def __init__(
        self,
        coordinator: TrovisCoordinator,
        description: TrovisSwitchDescription,
    ) -> None:
        super().__init__(
            coordinator,
            description.key,
            description.component,
            "switch",
            translation_key=description.translation_key,
            translation_placeholders=description.translation_placeholders,
        )
        self.entity_description = description

        self._boolean_metadata: BooleanMetadata = require_boolean_metadata(
            self._subsystem,
            description.field,
        )

        self._attr_entity_category = description.entity_category
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    def _to_ha_bool(self, value: bool) -> bool:
        """Convert the controller value to Home Assistant switch semantics."""
        result = bool(value)
        if self._boolean_metadata.inverted:
            return not result
        return result

    def _from_ha_bool(self, value: bool) -> bool:
        """Convert Home Assistant switch semantics to controller value."""
        if self._boolean_metadata.inverted:
            return not value
        return value

    @property
    def is_on(self) -> bool | None:
        """Return whether the switch is on."""
        value = getattr(self._subsystem, self.entity_description.field)
        if value is None:
            return None

        return self._to_ha_bool(bool(value))

    async def async_turn_on(self, **kwargs: object) -> None:
        """Turn the switch on."""
        await self._async_set_switch(self._from_ha_bool(True))

    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn the switch off."""
        await self._async_set_switch(self._from_ha_bool(False))

    async def _async_set_switch(self, value: bool) -> None:
        """Set the switch state."""
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