"""Constants for the Trovis 557x integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "trovis557x"

CONF_CONNECTION_TYPE: Final = "connection_type"
CONF_UNIT_ID: Final = "unit_id"

CONNECTION_TCP: Final = "tcp"
CONNECTION_SERIAL: Final = "serial"

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 246  # the controller's default Modbus station address

# The Trovis 557x serial line is fixed at 19200 8N1 (the PA6 default); only the
# port itself is asked for.
SERIAL_BAUDRATE: Final = 19200
SERIAL_BYTESIZE: Final = 8
SERIAL_PARITY: Final = "N"
SERIAL_STOPBITS: Final = 1

# A heating controller changes slowly, but we poll aggressively and fixed.
SCAN_INTERVAL: Final = timedelta(seconds=30)
