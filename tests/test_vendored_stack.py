"""The vendored libraries must work end-to-end exactly as the component uses them.

This exercises the real integration data path (connect -> ModbusUnit ->
Trovis557x.async_update) without needing a running Home Assistant. This variant
is backed by tmodbus.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import UNIT_ID

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "trovis557x"


async def test_vendored_imports() -> None:
    import modbus_connection
    import modbus_connection.tmodbus
    import trovis_modbus

    assert hasattr(modbus_connection, "ModbusUnit")
    assert hasattr(modbus_connection.tmodbus, "connect_tcp")
    assert hasattr(trovis_modbus, "Trovis557x")
    # pymodbus backend is intentionally NOT vendored.
    assert not (COMPONENT / "vendor" / "modbus_connection" / "pymodbus").exists()


async def test_end_to_end_through_vendor(server: tuple[str, int]) -> None:
    from modbus_connection.tmodbus import connect_tcp
    from trovis_modbus import OperatingMode, Trovis557x

    host, port = server
    # RTU-over-TCP gateway; tmodbus backend.
    conn = await connect_tcp(host, port=port, unit_id=UNIT_ID, framer="rtu")
    try:
        device = Trovis557x(conn.for_unit(UNIT_ID))
        await device.async_update()
        assert device.info.model == "Trovis 5579"
        assert device.sensors.outside_1 == pytest.approx(12.3)
        assert device.heating_circuit_1.pump_running is True
        assert device.heating_circuit_1.mode is OperatingMode.AUTOMATIC
        assert device.hot_water.setpoint_active == pytest.approx(50.0)
    finally:
        await conn.close()


def test_manifest_valid() -> None:
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    assert manifest["domain"] == "trovis557x"
    assert manifest["config_flow"] is True
    assert any("tmodbus" in req for req in manifest["requirements"])
    assert "trovis_modbus" in manifest["loggers"]


def test_strings_and_translation_valid() -> None:
    strings = json.loads((COMPONENT / "strings.json").read_text())
    en = json.loads((COMPONENT / "translations" / "en.json").read_text())
    assert "network" in strings["config"]["step"]
    assert "serial" in strings["config"]["step"]
    assert strings == en
