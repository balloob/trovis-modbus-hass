"""Water heater platform - the domestic hot water circuit (Rk4)."""

from __future__ import annotations
from typing import Any
from dataclasses import dataclass

from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)

from trovis_modbus import (
    HotWater,
    OperatingMode,
    TrovisWriteAccessDisabledError,
    TrovisWriteAccessError,
    TrovisWriteNotImplementedError,
    TrovisValueValidationError
)

from .metadata import (
    ha_unit_from_number,
    require_enum_metadata,
    require_number_metadata,
)
from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity
from ._local_dev import apply_local_trovis_modbus_override
apply_local_trovis_modbus_override()


# Operation-list labels <-> controller modes.
_MODES = {
    "auto": OperatingMode.AUTOMATIC,
    "on": OperatingMode.DAY,
    "off": OperatingMode.STANDBY,
}
_REVERSE = {mode: label for label, mode in _MODES.items()}


@dataclass(frozen=True, kw_only=True)
class TrovisWaterHeaterDescription(WaterHeaterEntityDescription):
    """Describes the domestic hot water entity."""
    component: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the hot water entity."""
    async_add_entities([TrovisHotWaterEntity(entry.runtime_data)])


class TrovisHotWaterEntity(TrovisEntity, WaterHeaterEntity):
    """Domestic hot water as a water heater."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = list(_MODES)

    def __init__(self, coordinator: TrovisCoordinator) -> None:
        description = TrovisWaterHeaterDescription(
            key="rk4dhw",
            translation_key="rk4dhw",
            component="hot_water",
        )
        super().__init__(
            coordinator,
            key=description.key,
            component=description.component,
            platform="water_heater",
            translation_key=description.translation_key,
        )
        self.entity_description = description
        temperature_metadata = require_number_metadata(self._hot_water, "setpoint_day")
        enum_metadata = require_enum_metadata(self._hot_water, "mode")

        self._enum_metadata = enum_metadata
        self._option_by_key = {
            option.key: option for option in enum_metadata.options
        }
        self._key_by_value = {
            int(option.value): option.key for option in enum_metadata.options
        }

        self._attr_operation_list = list(self._option_by_key)
        self._attr_min_temp = temperature_metadata.min_value
        self._attr_max_temp = temperature_metadata.max_value
        self._attr_target_temperature_step = temperature_metadata.step
        self._attr_temperature_unit = (
            ha_unit_from_number(temperature_metadata) or UnitOfTemperature.CELSIUS
        )


    @property
    def _hot_water(self) -> HotWater:
        return self._subsystem  # type: ignore[return-value]


    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.sensors.sf1


    @property
    def target_temperature(self) -> float | None:
        return self._hot_water.setpoint_active


    @property
    def min_temp(self) -> float:
        return self._hot_water.setpoint_min or 20.0


    @property
    def max_temp(self) -> float:
        return self._hot_water.setpoint_max or 90.0

    @property
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
        mode = self._hot_water.mode
        if mode is None:
            return None

        try:
            return self._key_by_value.get(int(mode))
        except (TypeError, ValueError):
            return None

    @property
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes."""
        return list(self._option_by_key)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if not self.coordinator.device.writing_enabled:
            raise HomeAssistantError("Please enable writing for changes!")

        try:
            await self._hot_water.async_write_datapoint(
                "setpoint_day",
                temperature,
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


    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set a new operation mode."""
        try:
            selected = self._option_by_key[operation_mode]
        except KeyError as err:
            raise HomeAssistantError(
                f"Unsupported TROVIS operation mode: {operation_mode}"
            ) from err

        if not self.coordinator.device.writing_enabled:
            raise HomeAssistantError("Please enable writing for changes!")

        try:
            await self._hot_water.async_write_datapoint(
                "mode",
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
