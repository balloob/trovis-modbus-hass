"""Real Home Assistant tests: config flow + entry setup against a live server."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trovis557x.const import (
    CONF_CONNECTION_TYPE,
    CONF_UNIT_ID,
    CONNECTION_TCP,
    DOMAIN,
)

from .conftest import UNIT_ID


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations, socket_enabled):  # noqa: ANN001
    yield


def _entry_data(host: str, port: int) -> dict:
    return {
        CONF_CONNECTION_TYPE: CONNECTION_TCP,
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_UNIT_ID: UNIT_ID,
    }


async def _setup(hass: HomeAssistant, server: tuple[str, int]) -> MockConfigEntry:
    host, port = server
    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(host, port))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_entry_creates_entities(
    hass: HomeAssistant, server: tuple[str, int]
) -> None:
    entry = await _setup(hass, server)
    assert entry.state is ConfigEntryState.LOADED

    # Controller-level diagnostic sensor (main device named after the model).
    outside = hass.states.get("sensor.trovis_5579_outside_temperature")
    assert outside is not None and outside.state == "12.3"

    # Per-circuit binary sensor on the circuit sub-device.
    pump = hass.states.get("binary_sensor.heating_circuit_1_pump")
    assert pump is not None and pump.state == "on"

    # The headline: a climate entity per heating circuit (its own sub-device).
    climate = hass.states.get("climate.heating_circuit_1")
    assert climate is not None
    assert climate.state == "auto"  # mode AUTOMATIC
    assert climate.attributes["temperature"] == 21.0  # room_setpoint_active
    assert climate.attributes["current_temperature"] == 20.0  # room_temperature

    water = hass.states.get("water_heater.hot_water")
    assert water is not None
    assert water.attributes["temperature"] == 50.0  # setpoint_active
    assert water.attributes["current_temperature"] == 45.0  # storage_temperature


async def test_sub_devices_via_controller(
    hass: HomeAssistant, server: tuple[str, int]
) -> None:
    """Each circuit / hot water is a sub-device linked via the controller."""
    entry = await _setup(hass, server)
    registry = dr.async_get(hass)

    controller = registry.async_get_device({(DOMAIN, entry.entry_id)})
    assert controller is not None

    circuit_1 = registry.async_get_device({(DOMAIN, f"{entry.entry_id}_circuit_1")})
    assert circuit_1 is not None
    assert circuit_1.via_device_id == controller.id
    assert circuit_1.name == "Heating circuit 1"

    hot_water = registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hot_water")})
    assert hot_water is not None
    assert hot_water.via_device_id == controller.id


async def test_climate_set_hvac_mode(
    hass: HomeAssistant, server: tuple[str, int]
) -> None:
    """Setting HVAC mode writes through the Ebene override and takes effect."""
    await _setup(hass, server)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.heating_circuit_1", "hvac_mode": "heat"},
        blocking=True,
    )
    await hass.async_block_till_done()

    climate = hass.states.get("climate.heating_circuit_1")
    assert climate is not None and climate.state == "heat"


async def test_config_flow_network_titles_from_model(
    hass: HomeAssistant, server: tuple[str, int]
) -> None:
    host, port = server
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "network"}
    )
    assert result["step_id"] == "network"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: host, CONF_PORT: port, CONF_UNIT_ID: UNIT_ID},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Trovis 5579"  # read from the device
    assert result["data"][CONF_CONNECTION_TYPE] == CONNECTION_TCP


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "network"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: 1, CONF_UNIT_ID: UNIT_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
