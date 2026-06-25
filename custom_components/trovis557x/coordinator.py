"""DataUpdateCoordinator that polls the Trovis controller."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusConnection, ModbusError
from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import Trovis557x

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type TrovisConfigEntry = ConfigEntry[TrovisCoordinator]


class TrovisCoordinator(DataUpdateCoordinator[Trovis557x]):
    """Owns the connection + device and refreshes every sub-system on a schedule.

    ``async_update`` fans out to each component (each reads only its own
    registers), so adding/removing entities never changes what is polled.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TrovisConfigEntry,
        connection: ModbusConnection,
        device: Trovis557x,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.connection = connection
        self.device = device

    async def _async_update_data(self) -> Trovis557x:
        try:
            await self.device.async_update()
        except ModbusError as err:
            raise UpdateFailed(f"Error communicating with Trovis: {err}") from err
        return self.device

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self.connection.close()
