"""Global temperature inputs not tied to a single circuit.

Per-circuit sensors (flow/return/room) live on :class:`HeatingCircuit`; storage
sensors live on :class:`HotWater`. Only the genuinely device-wide inputs remain
here.
"""

from __future__ import annotations

from .model import TrovisComponent, temperature


class Sensors(TrovisComponent):
    """Controller-wide temperature inputs."""

    # Trailing labels are the controller's sensor terminals (AF1, VF4, ...).
    outside_1 = temperature(9)  # AF1
    outside_2 = temperature(10)  # AF2
    flow_4 = temperature(15)  # VF4
    storage_remote = temperature(24)  # SF3/FG3
    remote_1 = temperature(25, unit="K")  # FG1
    remote_2 = temperature(26, unit="K")  # FG2
