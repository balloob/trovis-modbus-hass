"""Config flow for Trovis 557x."""

from __future__ import annotations

from contextlib import suppress
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from homeassistant.util import slugify
from modbus_connection import ModbusConnection, ModbusError
from modbus_connection.tmodbus import connect_serial, connect_tcp

from ._local_dev import apply_local_trovis_modbus_override

apply_local_trovis_modbus_override()

from trovis_modbus import DEFAULT_WRITE_ACCESS_CODE, Trovis557x

from .const import (
    CONF_ACCESS_CODE,
    CONF_CONNECTION_TYPE,
    CONF_DETECTED_SENSORS,
    CONF_MODEL,
    CONF_NETWORK_FRAMER,
    CONF_SLUG,
    CONF_UNIT_ID,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DEFAULT_PORT,
    DEFAULT_SLUG,
    DEFAULT_UNIT_ID,
    DOMAIN,
    NETWORK_FRAMER_RTU,
    NETWORK_FRAMER_SOCKET,
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
    """Return the device setup schema."""
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
    """Open the connection described by a config entry."""
    unit_id = int(data[CONF_UNIT_ID])

    if data[CONF_CONNECTION_TYPE] == CONNECTION_SERIAL:
        return await connect_serial(
            data[CONF_DEVICE],
            baudrate=SERIAL_BAUDRATE,
            bytesize=SERIAL_BYTESIZE,
            parity=SERIAL_PARITY,
            stopbits=SERIAL_STOPBITS,
        )

    return await connect_tcp(
        data[CONF_HOST],
        port=int(data[CONF_PORT]),
        framer=data.get(CONF_NETWORK_FRAMER, NETWORK_FRAMER_RTU),
    )


async def _async_probe_once(
    data: dict[str, Any],
) -> tuple[int, tuple[str, ...]] | None:
    """Probe one specific connection configuration."""
    connection: ModbusConnection | None = None

    try:
        connection = await open_connection(data)
        probe = await Trovis557x.async_probe(
            connection.for_unit(int(data[CONF_UNIT_ID]))
        )
        return probe.model, probe.detected_sensors
    except (ModbusError, OSError, ValueError):
        return None
    finally:
        if connection is not None:
            with suppress(ModbusError, OSError):
                await connection.close()


async def _async_probe(
    data: dict[str, Any],
) -> tuple[int, tuple[str, ...], str | None] | None:
    """Probe the controller and detect network framing when necessary."""
    if data[CONF_CONNECTION_TYPE] == CONNECTION_SERIAL:
        result = await _async_probe_once(data)
        if result is None:
            return None

        model, detected_sensors = result
        return model, detected_sensors, None

    stored_framer = data.get(CONF_NETWORK_FRAMER)
    framers = (
        (stored_framer,)
        if stored_framer is not None
        else (NETWORK_FRAMER_RTU, NETWORK_FRAMER_SOCKET)
    )

    for framer in framers:
        probe_data = {
            **data,
            CONF_NETWORK_FRAMER: framer,
        }
        result = await _async_probe_once(probe_data)

        if result is not None:
            model, detected_sensors = result
            return model, detected_sensors, framer

    return None


class TrovisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trovis 557x."""

    VERSION = 1

    _pending_data: dict[str, Any] | None = None
    _detected_model: int | None = None
    _detected_sensors: tuple[str, ...] = ()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TrovisOptionsFlow:
        """Create the options flow."""
        return TrovisOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Let the user choose the transport."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["network", "serial"],
        )

    async def async_step_network(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure an automatically detected network connection."""
        return await self._connection_step(
            CONNECTION_TCP,
            "network",
            STEP_NETWORK,
            user_input,
        )

    async def async_step_serial(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure a Modbus serial RTU connection."""
        return await self._connection_step(
            CONNECTION_SERIAL,
            "serial",
            STEP_SERIAL,
            user_input,
        )

    async def _connection_step(
        self,
        connection_type: str,
        step_id: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate the connection and continue device setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_CONNECTION_TYPE: connection_type,
                **user_input,
            }
            probe = await _async_probe(data)

            if probe is None:
                errors["base"] = "cannot_connect"
            else:
                model, detected_sensors, network_framer = probe

                if network_framer is not None:
                    data[CONF_NETWORK_FRAMER] = network_framer

                self._pending_data = data
                self._detected_model = model
                self._detected_sensors = detected_sensors
                return await self.async_step_device()

        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Let the user choose display name and entity ID prefix."""
        if self._pending_data is None or self._detected_model is None:
            return await self.async_step_user()

        default_name = f"Trovis {self._detected_model}"
        default_slug = _normalize_slug(default_name)

        if user_input is not None:
            name = _normalize_name(user_input.get(CONF_NAME), default_name)
            slug = _normalize_slug(user_input.get(CONF_SLUG) or name)

            data = {
                **self._pending_data,
                CONF_NAME: name,
                CONF_SLUG: slug,
                CONF_ACCESS_CODE: int(
                    user_input.get(
                        CONF_ACCESS_CODE,
                        DEFAULT_WRITE_ACCESS_CODE,
                    )
                ),
                CONF_MODEL: self._detected_model,
                CONF_DETECTED_SENSORS: list(self._detected_sensors),
            }

            return self.async_create_entry(
                title=name,
                data=data,
            )

        return self.async_show_form(
            step_id="device",
            data_schema=_device_schema(default_name, default_slug),
            errors={},
        )


class TrovisOptionsFlow(OptionsFlowWithReload):
    """Refresh automatically detected TROVIS properties."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Re-detect model, network framing and connected sensors."""
        probe = await _async_probe(dict(self.config_entry.data))

        if probe is None:
            return self.async_abort(reason="cannot_connect")

        model, detected_sensors, network_framer = probe

        if (
            network_framer is not None
            and self.config_entry.data.get(CONF_NETWORK_FRAMER)
            != network_framer
        ):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_NETWORK_FRAMER: network_framer,
                },
            )

        known_sensors = self.config_entry.options.get(
            CONF_DETECTED_SENSORS,
            self.config_entry.data.get(CONF_DETECTED_SENSORS, ()),
        )

        return self.async_create_entry(
            data={
                CONF_MODEL: model,
                CONF_DETECTED_SENSORS: sorted(
                    set(known_sensors) | set(detected_sensors)
                ),
            }
        )