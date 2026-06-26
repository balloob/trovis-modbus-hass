"""Climate platform — one entity per space-heating circuit (RK1-3)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import HeatingCircuit, OperatingMode

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity

_TO_HVAC = {
    OperatingMode.STANDBY: HVACMode.OFF,
    OperatingMode.AUTOMATIC: HVACMode.AUTO,
    OperatingMode.PROGRAM: HVACMode.AUTO,
    OperatingMode.DAY: HVACMode.HEAT,
    OperatingMode.NIGHT: HVACMode.HEAT,
    OperatingMode.MANUAL: HVACMode.HEAT,
}
_FROM_HVAC = {
    HVACMode.OFF: OperatingMode.STANDBY,
    HVACMode.AUTO: OperatingMode.AUTOMATIC,
    HVACMode.HEAT: OperatingMode.DAY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a climate entity per heating circuit."""
    coordinator = entry.runtime_data
    async_add_entities(
        TrovisHeatingCircuitClimate(coordinator, index) for index in (1, 2, 3)
    )


class TrovisHeatingCircuitClimate(TrovisEntity, ClimateEntity):
    """A heating circuit as a thermostat (room setpoint + mode)."""

    _attr_name = None  # primary entity -> takes the sub-device's name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 5
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: TrovisCoordinator, index: int) -> None:
        super().__init__(
            coordinator,
            key=f"climate_circuit{index}",
            component=f"heating_circuit_{index}",
            platform="climate",
        )

    @property
    def _circuit(self) -> HeatingCircuit:
        return self._subsystem  # type: ignore[return-value]

    # @property
    # def current_temperature(self) -> float | None:
    #     return self._circuit.room_temperature
    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature.
        Physical room sensors are exposed centrally through the Sensors component.
        They are not assigned to heating circuits here because the mapping depends
        on the configured hydraulic scheme.
        --> ToDo: Evaluate if hard coded connection to heating circuits, likely no
        """
        return None

    @property
    def target_temperature(self) -> float | None:
        return self._circuit.room_setpoint_active

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = self._circuit.mode
        return _TO_HVAC.get(mode) if mode is not None else None

    @property
    def hvac_action(self) -> HVACAction | None:
        if self._circuit.mode is OperatingMode.STANDBY:
            return HVACAction.OFF
        if self._circuit.pump_running is None:
            return None
        return HVACAction.HEATING if self._circuit.pump_running else HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._circuit.set_room_setpoint_day(temperature)
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._circuit.set_mode(_FROM_HVAC[hvac_mode])
        await self.coordinator.async_request_refresh()
