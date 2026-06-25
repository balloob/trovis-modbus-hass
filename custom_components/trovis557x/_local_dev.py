"""Local development helpers for the TROVIS 557x integration.

This module is intentionally safe for normal installations:
it only does something when a non-committed local_dev.py exists.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


def apply_local_trovis_modbus_override() -> None:
    """Prefer a local trovis_modbus checkout during development.

    Create custom_components/trovis557x/local_dev.py with:

        LOCAL_TROVIS_MODBUS_SRC = "/config/dev/trovis-modbus/src"

    The file is gitignored and must never be committed.
    """
    try:
        from .local_dev import LOCAL_TROVIS_MODBUS_SRC
    except ImportError:
        return

    src_path = Path(LOCAL_TROVIS_MODBUS_SRC)

    if not src_path.exists():
        _LOGGER.warning(
            "Local trovis_modbus override configured but path does not exist: %s",
            src_path,
        )
        return

    src_path_str = str(src_path)

    if src_path_str not in sys.path:
        sys.path.insert(0, src_path_str)
        _LOGGER.warning(
            "Using local trovis_modbus checkout from %s",
            src_path_str,
        )
