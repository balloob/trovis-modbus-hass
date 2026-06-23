"""Fixtures for the integration tests: a real Modbus TCP server + vendor path."""

from __future__ import annotations

import asyncio
import socket
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPONENT = REPO_ROOT / "custom_components" / "trovis557x"
VENDOR = COMPONENT / "vendor"
# Make `custom_components.trovis557x` importable, and the vendored libs too.
for path in (REPO_ROOT, VENDOR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pymodbus import FramerType  # noqa: E402
from pymodbus.datastore import (  # noqa: E402
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
from pymodbus.server import ModbusTcpServer  # noqa: E402

UNIT_ID = 247

HOLDING = {
    0: 5579,  # model
    2: 305,  # firmware -> 3.05
    3: 110,  # hardware -> 1.10
    5: 12345,  # serial
    9: 123,  # outside_1 -> 12.3
    19: 200,  # room_1 -> 20.0
    22: 450,  # storage_1 -> 45.0
    98: 900,  # max flow setpoint -> 90.0
    99: 1430,  # time
    100: 2106,  # date
    101: 2026,  # year
    102: 1,  # switch_top -> AUTOMATIC
    105: 1,  # hc1 mode -> AUTOMATIC
    106: 42,  # hc1 control signal
    111: 1,  # hot_water mode -> AUTOMATIC
    999: 550,  # hc1 flow_setpoint -> 55.0
    1000: 800,  # hc1 flow_max
    1001: 200,  # hc1 flow_min
    1002: 210,  # hc1 room_setpoint_day -> 21.0
    1003: 180,  # hc1 room_setpoint_night
    1004: 210,  # hc1 room_setpoint_active -> 21.0
    1005: 12,  # hc1 slope
    1006: 0,  # hc1 level
    1799: 500,  # hot_water setpoint_day -> 50.0
    1800: 600,  # hot_water setpoint_max
    1801: 450,  # hot_water setpoint_min
    1807: 500,  # hot_water setpoint_active -> 50.0
    1837: 670,  # hot_water active_charge_setpoint -> 67.0
}
COILS = {
    56: True,  # hc1 pump
    999: True,  # hc1 automatic
    1000: True,  # hc1 day active
    59: True,  # hot_water charge pump
    1799: True,  # hot_water automatic
}


def _block(
    mapping: dict[int, int | bool], size: int = 2000
) -> ModbusSequentialDataBlock:
    values = [0] * (size + 1)
    for address, value in mapping.items():
        values[address + 1] = int(value)
    return ModbusSequentialDataBlock(0, values)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def server(socket_enabled) -> AsyncIterator[tuple[str, int]]:  # noqa: ANN001
    # `socket_enabled` (from pytest-homeassistant-custom-component) lifts the
    # default socket ban so the in-process Modbus server can bind/accept.
    device = ModbusDeviceContext(
        co=_block(COILS), hr=_block(HOLDING), di=_block({}), ir=_block({})
    )
    context = ModbusServerContext(devices={UNIT_ID: device}, single=False)
    host, port = "127.0.0.1", _free_port()
    # The integration speaks RTU-over-TCP, so the test gateway does too.
    srv = ModbusTcpServer(context, framer=FramerType.RTU, address=(host, port))
    task = asyncio.create_task(srv.serve_forever())
    for _ in range(100):
        try:
            _, writer = await asyncio.open_connection(host, port)
        except OSError:
            await asyncio.sleep(0.02)
            continue
        writer.close()
        await writer.wait_closed()
        break
    try:
        yield host, port
    finally:
        await srv.shutdown()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
