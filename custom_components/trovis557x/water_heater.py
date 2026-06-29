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
        return _REVERSE.get(self._hot_water.mode)


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
        except (TrovisWriteAccessDisabledError, TrovisWriteAccessError) as err:
            raise HomeAssistantError(str(err)) from err
        except TrovisWriteNotImplementedError as err:
            raise HomeAssistantError(
                "Writing TROVIS data points is not implemented yet"
            ) from err

        await self.coordinator.async_request_refresh()


    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set a new operation mode."""
        if operation_mode not in _MODES:
            raise HomeAssistantError(
                f"Unsupported TROVIS operation mode: {operation_mode}"
            )

        if not self.coordinator.device.writing_enabled:
            raise HomeAssistantError("Please enable writing for changes!")

        try:
            await self._hot_water.async_write_datapoint(
                "mode",
                _MODES[operation_mode],
                access_code=self.coordinator.access_code,
            )
        except (TrovisWriteAccessDisabledError, TrovisWriteAccessError) as err:
            raise HomeAssistantError(str(err)) from err
        except TrovisWriteNotImplementedError as err:
            raise HomeAssistantError(
                "Writing TROVIS data points is not implemented yet"
            ) from err

        await self.coordinator.async_request_refresh()
