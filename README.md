# Samson Trovis 557x — Home Assistant integration

A Home Assistant **custom integration** for the Samson Trovis 557x heating
controller, talking Modbus directly (TCP or serial). It surfaces the full sensor
set of the original [`samson_trovis_557x`](https://github.com/Tom-Bom-badil/samson_trovis_557x)
YAML package as proper UI entities — no YAML, no helpers, set up entirely from
the UI.

It is **self-contained**: the connection layer (`modbus_connection` + its
tmodbus backend) and the device library (`trovis_modbus`) are vendored into the
component under `vendor/`, so you can install it from a zip with no extra repos.
Home Assistant installs the external requirements, `tmodbus` + `serialx`,
automatically.

## Install

1. Download / clone this repo.
2. Copy the `custom_components/trovis557x` folder into your Home Assistant
   config directory so you end up with:

   ```
   <config>/custom_components/trovis557x/
   ```

   (If you downloaded a zip, unzip it and copy that folder.)
3. **Restart Home Assistant.**
4. Go to **Settings → Devices & Services → Add Integration**, search for
   **“Samson Trovis 557x”**, and follow the flow.

## Configuration

The flow asks how the controller is connected:

- **Network (Modbus TCP)** — host + port (default `502`).
- **Serial (Modbus RTU)** — serial port (e.g. `/dev/ttyUSB0`), baud rate,
  parity, stop/byte bits.

plus the **Modbus address** (unit ID, default `247`) and a **polling interval**.
The connection is opened and probed during setup, so a wrong host/port/device is
reported immediately. The polling interval can be changed later via the
integration’s **Configure** (options) button.

## What you get

One device, with proper entity types per sub-system:

- **Climate** — one thermostat **per heating circuit** (RK1–3): current room
  temperature, target room setpoint, and HVAC mode (auto / heat / off).
- **Water heater** — the domestic hot water circuit (HK4): target setpoint and
  operation mode.
- **Sensors** — temperature probes (outside / flow / return / room / storage),
  per-circuit flow setpoint and valve position, hot-water setpoints, rotary
  switch positions, controller clock, firmware (diagnostic).
- **Binary sensors** — circulation/charge pumps, collective fault, frost
  protection, standby, hot-water charging and disinfection.

## How it works

Trovis is a **direct** Modbus connection — you do **not** need any separate
Modbus integration. On setup the component builds a tmodbus-backed connection
via the vendored `modbus_connection.tmodbus` (`connect_tcp` / `connect_serial`),
takes a `ModbusUnit` for the configured address, and hands it to the vendored
`trovis_modbus` library. A `DataUpdateCoordinator` polls on your interval; if the
link drops the entry reloads to re-establish it.

## Updating the vendored libraries

The vendored copies are produced by `scripts/vendor.sh` from the sibling
`modbus-connection` and `trovis-modbus` source repos. Re-run it after changing
either library:

```bash
./scripts/vendor.sh
```

## Develop / test

```bash
uv sync
uv run pytest
```

The suite verifies the vendored stack end-to-end against a real in-process
Modbus server and runs the config flow + entry setup inside a real Home
Assistant via `pytest-homeassistant-custom-component`.

Formatting/linting is [ruff](https://docs.astral.sh/ruff/), enforced in CI (the
vendored libraries are excluded — they are linted in their own repos). Install
the commit hook with [prek](https://github.com/j178/prek):

```bash
uvx prek install          # format on commit
uvx prek run --all-files  # format + lint everything now
```
