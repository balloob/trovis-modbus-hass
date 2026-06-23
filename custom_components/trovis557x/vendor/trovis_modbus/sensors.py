"""Global temperature inputs not tied to a single circuit.

Per-circuit sensors (flow/return/room) live on :class:`HeatingCircuit`; storage
sensors live on :class:`HotWater`. Only the genuinely device-wide inputs remain
here.
"""

from __future__ import annotations

from .component import Component, temperature


class Sensors(Component):
    """Controller-wide temperature inputs."""

    outside_1 = temperature(9, doc="Outside sensor AF1")
    outside_2 = temperature(10, doc="Outside sensor AF2")
    flow_4 = temperature(15, doc="Flow sensor VF4")
    storage_remote = temperature(24, doc="Storage/remote sensor SF3/FG3")
    remote_1 = temperature(25, unit="K", doc="Remote adjuster FG1")
    remote_2 = temperature(26, unit="K", doc="Remote adjuster FG2")
