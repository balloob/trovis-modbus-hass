"""The Samson Trovis 557x integration.

Trovis is a direct Modbus connection. The integration owns the connection and
hands its ModbusUnit to trovis-modbus.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from modbus_connection import ModbusConnectionError, ModbusError

from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import Trovis557x

from .config_flow import open_connection
from .const import (
    CONF_DETECTED_SENSORS,
    CONF_MODEL,
    CONF_UNIT_ID,
)
from .coordinator import TrovisConfigEntry, TrovisCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
) -> bool:
    """Set up Trovis 557x from a config entry."""
    try:
        connection = await open_connection(dict(entry.data))
    except ModbusConnectionError as err:
        raise ConfigEntryNotReady(
            f"Could not connect to Trovis: {err}"
        ) from err

    unit = connection.for_unit(int(entry.data[CONF_UNIT_ID]))
    settings = {**entry.data, **entry.options}

    # Upgrade entries created before automatic model/sensor detection.
    if (
        CONF_MODEL not in settings
        or CONF_DETECTED_SENSORS not in settings
    ):
        try:
            probe = await Trovis557x.async_probe(unit)
        except (ModbusError, OSError, ValueError) as err:
            await connection.close()
            raise ConfigEntryNotReady(
                f"Could not probe Trovis: {err}"
            ) from err

        data = {
            **entry.data,
            CONF_MODEL: probe.model,
            CONF_DETECTED_SENSORS: list(probe.detected_sensors),
        }
        hass.config_entries.async_update_entry(entry, data=data)
        settings = {**data, **entry.options}

    try:
        device = Trovis557x(
            unit,
            model=int(settings[CONF_MODEL]),
            detected_sensors=settings[CONF_DETECTED_SENSORS],
        )
    except ValueError as err:
        await connection.close()
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = TrovisCoordinator(hass, entry, connection, device)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await connection.close()
        raise

    entry.runtime_data = coordinator

    entry.async_on_unload(
        connection.on_connection_lost(
            lambda: hass.config_entries.async_schedule_reload(entry.entry_id)
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
) -> bool:
    """Unload a config entry and close the owned connection."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unloaded:
        await entry.runtime_data.connection.close()

    return unloaded