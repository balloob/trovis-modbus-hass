"""The Samson Trovis 557x integration.

Trovis is a DIRECT Modbus connection: this integration owns the connection. The
config flow asks for Network (TCP) or Serial; either choice builds a
tmodbus-backed connection via ``modbus_connection.tmodbus``, gets a
``ModbusUnit`` and hands it to the ``trovis_modbus`` library.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from modbus_connection import ModbusConnectionError
from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import Trovis557x

from .config_flow import open_connection
from .const import CONF_UNIT_ID
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


async def async_setup_entry(hass: HomeAssistant, entry: TrovisConfigEntry) -> bool:
    """Set up Trovis 557x from a config entry."""
    try:
        connection = await open_connection(dict(entry.data))
    except ModbusConnectionError as err:
        raise ConfigEntryNotReady(f"Could not connect to Trovis: {err}") from err

    device = Trovis557x(connection.for_unit(int(entry.data[CONF_UNIT_ID])))
    coordinator = TrovisCoordinator(hass, entry, connection, device)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await connection.close()
        raise

    entry.runtime_data = coordinator

    # The connection is transient: on a drop, reload to rebuild it. The poll
    # failure (UpdateFailed) is the reliable backstop if the callback is missed.
    entry.async_on_unload(
        connection.on_connection_lost(
            lambda: hass.config_entries.async_schedule_reload(entry.entry_id)
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TrovisConfigEntry) -> bool:
    """Unload a config entry and close the owned connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.connection.close()
    return unloaded
