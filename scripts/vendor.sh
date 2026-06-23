#!/usr/bin/env bash
# Re-vendor modbus-connection (protocol + tmodbus impl) and trovis-modbus into
# the custom component, so it installs from a zip with no access to the private
# source repos. Run from anywhere; paths are resolved relative to this script.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
vendor="$root/custom_components/trovis557x/vendor"
mc="$root/../modbus-connection/src/modbus_connection"
tm="$root/../trovis-modbus/src/trovis_modbus"

rm -rf "$vendor"
mkdir -p "$vendor/modbus_connection/tmodbus" "$vendor/trovis_modbus"

# modbus_connection: top-level interface + tmodbus backend only (no pymodbus).
cp "$mc"/{__init__.py,_protocol.py,_types.py,exceptions.py,py.typed} "$vendor/modbus_connection/"
cp "$mc"/tmodbus/__init__.py "$vendor/modbus_connection/tmodbus/"

# trovis_modbus: the whole library.
cp "$tm"/*.py "$vendor/trovis_modbus/"
cp "$tm"/py.typed "$vendor/trovis_modbus/"

echo "Vendored into $vendor"
