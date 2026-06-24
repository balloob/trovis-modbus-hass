"""The controller's readable Modbus address ranges.

The Trovis only answers reads that fall inside specific contiguous ranges; the
addresses *between* ranges are not readable, and a read that crosses a gap is
rejected. These are the ``register_bereiche`` / ``coil_bereiche`` from the
upstream SmartHomeNG plugin (the 7576 set, plus the 7579 heating-circuit-3
ranges so all three circuits are covered).

The block planner uses these to merge reads only *within* a range and never
across a gap, while still clipping each read to the addresses actually used — so
e.g. a circuit's 999-1011 and 1032 become one read (both inside ``[999, 1044]``)
but 1062 stays separate (it lives in ``[1053, 1071]``).
"""

from __future__ import annotations

# (low, high) inclusive — sorted, non-overlapping.
REGISTER_RANGES: tuple[tuple[int, int], ...] = (
    (0, 6),
    (9, 40),
    (98, 154),
    (159, 166),
    (200, 214),
    (299, 319),
    (999, 1044),
    (1053, 1071),
    (1089, 1095),
    (1199, 1243),
    (1255, 1271),
    (1399, 1443),
    (1455, 1471),
    (1799, 1812),
    (1827, 1839),
    (1855, 1870),
    (6469, 6525),
)

COIL_RANGES: tuple[tuple[int, int], ...] = (
    (0, 39),
    (56, 68),
    (87, 112),
    (115, 123),
    (129, 167),
    (175, 214),
    (221, 237),
    (244, 308),
    (321, 337),
    (997, 1008),
    (1016, 1018),
    (1024, 1044),
    (1199, 1208),
    (1211, 1212),
    (1216, 1218),
    (1224, 1237),
    (1399, 1408),
    (1411, 1412),
    (1416, 1418),
    (1424, 1437),
    (1799, 1808),
    (1824, 1844),
)
