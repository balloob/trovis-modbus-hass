"""Config flow for Trovis 557x."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
)
from modbus_connection import ModbusConnection, ModbusError
from modbus_connection.tmodbus import connect_serial, connect_tcp
from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import Trovis557x

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_UNIT_ID,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    SERIAL_BAUDRATE,
    SERIAL_BYTESIZE,
    SERIAL_PARITY,
    SERIAL_STOPBITS,
)

_UNIT = NumberSelector(
    NumberSelectorConfig(min=1, max=255, step=1, mode=NumberSelectorMode.BOX)
)

STEP_NETWORK = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): _UNIT,
    }
)

STEP_SERIAL = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): _UNIT,
    }
)


async def open_connection(data: dict[str, Any]) -> ModbusConnection:
    """Open the connection described by a config entry (caller closes it).

    Backed by tmodbus. Network uses RTU-over-TCP framing — a Trovis is a serial
    RTU device, and the gateways used to reach it over Ethernet are transparent
    (they carry RTU frames, not native Modbus TCP). Reach a network gateway via
    the Network option, not a ``socket://`` serial URL. The serial line is fixed
    at 19200 8N1.
    """
    unit_id = int(data[CONF_UNIT_ID])
    if data[CONF_CONNECTION_TYPE] == CONNECTION_SERIAL:
        return await connect_serial(
            data[CONF_DEVICE],
            baudrate=SERIAL_BAUDRATE,
            bytesize=SERIAL_BYTESIZE,
            parity=SERIAL_PARITY,
            stopbits=SERIAL_STOPBITS,
            unit_id=unit_id,
        )
    return await connect_tcp(
        data[CONF_HOST], port=data[CONF_PORT], unit_id=unit_id, framer="rtu"
    )


class TrovisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trovis 557x."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose the transport."""
        return self.async_show_menu(step_id="user", menu_options=["network", "serial"])

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a Modbus TCP connection."""
        return await self._connection_step(
            CONNECTION_TCP, "network", STEP_NETWORK, user_input
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a Modbus serial (RTU) connection."""
        return await self._connection_step(
            CONNECTION_SERIAL, "serial", STEP_SERIAL, user_input
        )

    async def _connection_step(
        self,
        connection_type: str,
        step_id: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_CONNECTION_TYPE: connection_type, **user_input}
            if (title := await self._async_title(data)) is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=title, data=data)
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def _async_title(self, data: dict[str, Any]) -> str | None:
        """Connect and read the controller model for the entry title."""
        try:
            connection = await open_connection(data)
        except (ModbusError, OSError, ValueError):
            return None
        try:
            device = Trovis557x(connection.for_unit(int(data[CONF_UNIT_ID])))
            await device.info.async_update()
            return device.info.model
        except ModbusError:
            return None
        finally:
            await connection.close()
