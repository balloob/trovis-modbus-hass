"""Make the vendored libraries importable.

`modbus_connection` (interface + pymodbus backend) and `trovis_modbus` are
bundled under ``vendor/`` so the component installs from a zip without access to
the private source repos. Importing this module puts that directory on
``sys.path``.

The package ``__init__`` imports this first; because Python always imports a
package before any of its submodules, every other component module can then
import the vendored libraries as ordinary top-level imports.
"""

from __future__ import annotations

import os
import sys

_VENDOR = os.path.join(os.path.dirname(__file__), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
