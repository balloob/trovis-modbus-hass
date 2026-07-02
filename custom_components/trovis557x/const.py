"""Constants for the Trovis 557x integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "trovis557x"

CONF_CONNECTION_TYPE: Final = "connection_type"
CONF_UNIT_ID: Final = "unit_id"
CONF_SLUG: Final = "slug"
CONF_ACCESS_CODE: Final = "access_code"
CONF_MODEL: Final = "model"
CONF_DETECTED_SENSORS: Final = "detected_sensors"
CONF_NETWORK_FRAMER: Final = "network_framer"

CONNECTION_TCP: Final = "tcp"
CONNECTION_SERIAL: Final = "serial"

NETWORK_FRAMER_RTU: Final = "rtu"
NETWORK_FRAMER_SOCKET: Final = "socket"

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 246
DEFAULT_SLUG: Final = "trovis"

# The Trovis serial line - 9.600 / 19200 baud (PA6; 5573 is fixed to 19.200)
SERIAL_BAUDRATE: Final = 19200
SERIAL_BYTESIZE: Final = 8
SERIAL_PARITY: Final = "N"
SERIAL_STOPBITS: Final = 1

# A heating controller is not an express train.
SCAN_INTERVAL: Final = timedelta(seconds=60)