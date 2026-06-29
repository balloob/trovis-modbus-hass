"""Config flow for Trovis 557x."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from homeassistant.util import slugify
from modbus_connection import ModbusConnection, ModbusError

# pymodbus
# from modbus_connection.pymodbus import connect_serial, connect_tcp
# tmodbus
from modbus_connection.tmodbus import connect_serial, connect_tcp

from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import Trovis557x, DEFAULT_WRITE_ACCESS_CODE

from .const import (
    CONF_ACCESS_CODE,
    CONF_CONNECTION_TYPE,
    CONF_SLUG,
    CONF_UNIT_ID,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DEFAULT_PORT,
    DEFAULT_SLUG,
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

_ACCESS_CODE = NumberSelector(
    NumberSelectorConfig(min=0, max=9999, step=1, mode=NumberSelectorMode.BOX)
)


def _normalize_slug(value: object) -> str:
    """Return a Home Assistant friendly entity prefix."""
    slug = slugify(str(value or ""))
    return re.sub(r"_+", "_", slug).strip("_") or DEFAULT_SLUG


def _normalize_name(value: object, fallback: str) -> str:
    """Return a non-empty display name."""
    name = str(value or "").strip()
    return name or fallback


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


def _device_schema(default_name: str, default_slug: str) -> vol.Schema:
    """Return the second setup step schema with suggested device values."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=default_name): TextSelector(),
            vol.Required(CONF_SLUG, default=default_slug): TextSelector(),
            vol.Required(
                CONF_ACCESS_CODE,
                default=DEFAULT_WRITE_ACCESS_CODE,
            ): _ACCESS_CODE,
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

        # tmodbus:
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

    #     # pymodbus:
    #     return await connect_serial(
    #         data[CONF_DEVICE],
    #         baudrate=SERIAL_BAUDRATE,
    #         bytesize=SERIAL_BYTESIZE,
    #         parity=SERIAL_PARITY,
    #         stopbits=SERIAL_STOPBITS,
    #     )
    # return await connect_tcp(
    #     data[CONF_HOST],port=data[CONF_PORT], framer="rtu",
    # )


class TrovisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trovis 557x."""

    VERSION = 1

    _pending_data: dict[str, Any] | None = None
    _detected_model: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose the transport."""
        return self.async_show_menu(step_id="user", menu_options=["network", "serial"])

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a network RTU-over-TCP connection."""
        return await self._connection_step(
            CONNECTION_TCP, "network", STEP_NETWORK, user_input
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a Modbus serial RTU connection."""
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
            detected_model = await self._async_detect_model(data)

            if detected_model is None:
                errors["base"] = "cannot_connect"
            else:
                self._pending_data = data
                self._detected_model = detected_model
                return await self.async_step_device()

        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose display name and entity ID prefix."""
        if self._pending_data is None or self._detected_model is None:
            return await self.async_step_user()

        default_name = self._detected_model
        default_slug = _normalize_slug(default_name)

        if user_input is not None:
            name = _normalize_name(user_input.get(CONF_NAME), default_name)
            slug = _normalize_slug(user_input.get(CONF_SLUG) or name)
            access_code = int(
                user_input.get(CONF_ACCESS_CODE, DEFAULT_WRITE_ACCESS_CODE)
            )

            data = {
                **self._pending_data,
                CONF_NAME: name,
                CONF_SLUG: slug,
                CONF_ACCESS_CODE: access_code,
            }

            return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="device",
            data_schema=_device_schema(default_name, default_slug),
            errors={},
        )

    async def _async_detect_model(self, data: dict[str, Any]) -> str | None:
        """Connect and read the controller model for setup suggestions."""
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