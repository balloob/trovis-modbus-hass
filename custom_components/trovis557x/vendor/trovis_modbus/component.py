"""Base classes: the self-updating ``Component`` and its field descriptors.

A ``RegisterField[T]`` / ``CoilField`` maps a Python attribute to a Modbus
register or coil; reading it returns the decoded value (typed ``T | None`` /
``bool | None``). Fields that need no post-processing are declared directly via
the typed factories below (``temperature(9)``); a value that needs shaping uses
a private field plus a normal ``@property`` so static typing stays accurate::

    _firmware_raw = gauge(2, 0.01, signed=False)

    @property
    def firmware_version(self) -> str | None:
        value = self._firmware_raw
        return f"{value:.2f}" if value is not None else None
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import time
from typing import TYPE_CHECKING, Any, overload

from modbus_connection import ModbusExceptionError

from .enums import OperatingMode, Weekday

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

NAN_INT16 = 0x7FFF  # sentinel the controller returns for an absent sensor
_MAX_GAP = 8  # merge registers/coils less than this many addresses apart
_MAX_SPAN = 100  # but never read a block wider than this

UpdateListener = Callable[[], None]


def _decimals(scale: float) -> int:
    """Number of decimals implied by a scale factor (0.1 -> 1, 0.01 -> 2)."""
    if scale >= 1:
        return 0
    return max(0, len(f"{scale:.10f}".rstrip("0").split(".")[1]))


class RegisterField[T]:
    """A holding register exposed as a typed attribute (returns ``T | None``)."""

    def __init__(
        self,
        address: int,
        *,
        scale: float = 1.0,
        signed: bool = True,
        writable: bool = False,
        nan: int | None = None,
        kind: str = "number",
        stride: int = 0,
        unit: str | None = None,
        level_coil: int | None = None,
        level_coil_stride: int = 0,
        doc: str = "",
    ) -> None:
        self.address = address
        self.scale = scale
        self.signed = signed
        self.writable = writable
        self.nan = nan
        self.kind = kind  # number | mode | weekday | time | raw
        self.stride = stride
        self.unit = unit
        # The "Ebene" override coil that must be set to 0 (remote control) before
        # this value can be written over Modbus; None if no override is needed.
        self.level_coil = level_coil
        self.level_coil_stride = level_coil_stride
        self._decimals = _decimals(scale)
        suffix = f" ({unit})" if unit else ""
        self.__doc__ = f"{doc}{suffix}".strip() or None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    if TYPE_CHECKING:

        @overload
        def __get__(self, obj: None, objtype: Any = ...) -> RegisterField[T]: ...

        @overload
        def __get__(self, obj: object, objtype: Any = ...) -> T | None: ...

    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        if obj is None:
            return self
        return obj._values.get(self.name)

    # -- codec ---------------------------------------------------------------

    def decode(self, raw: int) -> Any:
        if self.nan is not None and raw == self.nan:
            return None
        if self.signed and raw >= 0x8000:
            raw -= 0x10000
        if self.kind == "raw":
            return raw
        if self.kind == "mode":
            try:
                return OperatingMode(raw)
            except ValueError:
                return None
        if self.kind == "weekday":
            return Weekday(raw) if 0 <= raw <= 7 else None
        if self.kind == "time":
            hour, minute = divmod(raw, 100)
            return time(hour=hour, minute=minute) if hour < 24 and minute < 60 else None
        value = raw * self.scale
        return int(value) if self._decimals == 0 else round(value, self._decimals)

    def encode(self, value: Any) -> int:
        if self.kind == "mode":
            raw = int(OperatingMode(value))
        elif self.kind == "weekday":
            raw = int(Weekday(value))
        elif self.kind == "time":
            raw = value.hour * 100 + value.minute
        elif self.scale != 1.0:
            raw = round(value / self.scale)
        else:
            raw = int(value)
        return raw & 0xFFFF if raw < 0 else raw


class CoilField:
    """A coil exposed as a ``bool | None`` attribute."""

    def __init__(
        self,
        address: int,
        *,
        writable: bool = False,
        stride: int = 0,
        level_coil: int | None = None,
        level_coil_stride: int = 0,
        doc: str = "",
    ) -> None:
        self.address = address
        self.writable = writable
        self.stride = stride
        self.level_coil = level_coil
        self.level_coil_stride = level_coil_stride
        self.__doc__ = doc or None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    if TYPE_CHECKING:

        @overload
        def __get__(self, obj: None, objtype: Any = ...) -> CoilField: ...

        @overload
        def __get__(self, obj: object, objtype: Any = ...) -> bool | None: ...

    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        if obj is None:
            return self
        return obj._coils.get(self.name)


# -- typed field factories ----------------------------------------------------


def temperature(
    address: int,
    *,
    stride: int = 0,
    writable: bool = False,
    level_coil: int | None = None,
    level_coil_stride: int = 0,
    unit: str = "°C",
    doc: str = "",
) -> RegisterField[float]:
    """A signed 0.1-scaled temperature register with the NaN sentinel."""
    return RegisterField(
        address,
        scale=0.1,
        signed=True,
        nan=NAN_INT16,
        stride=stride,
        writable=writable,
        level_coil=level_coil,
        level_coil_stride=level_coil_stride,
        unit=unit,
        doc=doc,
    )


def gauge(
    address: int,
    scale: float,
    *,
    signed: bool = True,
    stride: int = 0,
    writable: bool = False,
    unit: str | None = None,
    doc: str = "",
) -> RegisterField[float]:
    """A scaled numeric register (slope, level, hysteresis, ...)."""
    return RegisterField(
        address,
        scale=scale,
        signed=signed,
        stride=stride,
        writable=writable,
        unit=unit,
        doc=doc,
    )


def integer(
    address: int,
    *,
    signed: bool = True,
    stride: int = 0,
    writable: bool = False,
    unit: str | None = None,
    doc: str = "",
) -> RegisterField[int]:
    """An unscaled integer register (counts, percentages, addresses)."""
    return RegisterField(
        address,
        scale=1.0,
        signed=signed,
        stride=stride,
        writable=writable,
        unit=unit,
        doc=doc,
    )


def operating_mode(
    address: int,
    *,
    stride: int = 0,
    writable: bool = False,
    level_coil: int | None = None,
    level_coil_stride: int = 0,
    doc: str = "",
) -> RegisterField[OperatingMode]:
    """An operating-mode register (``Liste_Schalter``)."""
    return RegisterField(
        address,
        kind="mode",
        stride=stride,
        writable=writable,
        level_coil=level_coil,
        level_coil_stride=level_coil_stride,
        doc=doc,
    )


def weekday_value(
    address: int, *, writable: bool = False, doc: str = ""
) -> RegisterField[Weekday]:
    """A weekday register (0 = off)."""
    return RegisterField(address, kind="weekday", writable=writable, doc=doc)


def time_value(
    address: int, *, writable: bool = False, doc: str = ""
) -> RegisterField[time]:
    """A time-of-day register (HHMM)."""
    return RegisterField(address, kind="time", writable=writable, doc=doc)


def raw_register(
    address: int, *, writable: bool = False, doc: str = ""
) -> RegisterField[int]:
    """A raw register word (no scaling/sign handling)."""
    return RegisterField(address, kind="raw", writable=writable, doc=doc)


def coil(
    address: int,
    *,
    writable: bool = False,
    stride: int = 0,
    level_coil: int | None = None,
    level_coil_stride: int = 0,
    doc: str = "",
) -> CoilField:
    """A coil."""
    return CoilField(
        address,
        writable=writable,
        stride=stride,
        level_coil=level_coil,
        level_coil_stride=level_coil_stride,
        doc=doc,
    )


def _blocks(items: Iterable[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Group (address, name) pairs into contiguous read blocks."""
    ordered = sorted(items)
    blocks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for address, name in ordered:
        if current and (
            address - current[-1][0] > _MAX_GAP or address - current[0][0] >= _MAX_SPAN
        ):
            blocks.append(current)
            current = []
        current.append((address, name))
    if current:
        blocks.append(current)
    return blocks


class Component:
    """A device sub-system whose attributes map to registers and coils.

    Subclasses declare ``RegisterField`` / ``CoilField`` descriptors (usually via
    the typed factories). Each component reads only its own registers, so it can
    refresh independently; listeners registered via :meth:`add_update_listener`
    fire after each update (one entity in Home Assistant can subscribe per
    component).
    """

    _register_fields: dict[str, RegisterField[Any]] = {}
    _coil_fields: dict[str, CoilField] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        registers: dict[str, RegisterField[Any]] = {}
        coils: dict[str, CoilField] = {}
        for klass in reversed(cls.__mro__):
            for name, value in vars(klass).items():
                if isinstance(value, RegisterField):
                    registers[name] = value
                elif isinstance(value, CoilField):
                    coils[name] = value
        cls._register_fields = registers
        cls._coil_fields = coils

    def __init__(self, unit: ModbusUnit, index: int = 1) -> None:
        self._unit = unit
        self._index = index
        self._values: dict[str, Any] = {}
        self._coils: dict[str, bool | None] = {}
        self._listeners: list[UpdateListener] = []

    def _address(self, field: RegisterField[Any] | CoilField) -> int:
        return field.address + field.stride * (self._index - 1)

    # -- listeners -----------------------------------------------------------

    def add_update_listener(self, listener: UpdateListener) -> Callable[[], None]:
        """Register a callback fired after each update; returns an unsubscribe."""
        self._listeners.append(listener)

        def remove() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return remove

    # -- update --------------------------------------------------------------

    async def async_update(self) -> None:
        """Read this component's registers and coils, then notify listeners."""
        await self._update_registers()
        await self._update_coils()
        for listener in list(self._listeners):
            listener()

    async def _update_registers(self) -> None:
        fields = self._register_fields
        if not fields:
            return
        addr_to_name = {self._address(f): name for name, f in fields.items()}
        for block in _blocks(addr_to_name.items()):
            start = block[0][0]
            count = block[-1][0] - start + 1
            try:
                words = await self._unit.read_holding_registers(start, count)
            except ModbusExceptionError:
                for _addr, name in block:
                    self._values[name] = None
                continue
            for address, name in block:
                self._values[name] = fields[name].decode(words[address - start])

    async def _update_coils(self) -> None:
        fields = self._coil_fields
        if not fields:
            return
        addr_to_name = {self._address(f): name for name, f in fields.items()}
        for block in _blocks(addr_to_name.items()):
            start = block[0][0]
            count = block[-1][0] - start + 1
            try:
                bits = await self._unit.read_coils(start, count)
            except ModbusExceptionError:
                for _addr, name in block:
                    self._coils[name] = None
                continue
            for address, name in block:
                self._coils[name] = bool(bits[address - start])

    # -- writes --------------------------------------------------------------

    async def write(self, field: str, value: Any) -> None:
        """Write a writable register or coil by attribute name.

        If the field has an override ("Ebene") coil, it is first set to 0
        (remote control) so the controller accepts the write — a documented
        Trovis quirk: e.g. the operating mode is ignored over Modbus unless its
        Ebene coil is released first.
        """
        if field in self._register_fields:
            register = self._register_fields[field]
            if not register.writable:
                raise AttributeError(f"{field} is read-only")
            await self._enable_remote_control(register)
            await self._unit.write_register(
                self._address(register), register.encode(value)
            )
        elif field in self._coil_fields:
            coil_field = self._coil_fields[field]
            if not coil_field.writable:
                raise AttributeError(f"{field} is read-only")
            await self._enable_remote_control(coil_field)
            await self._unit.write_coil(self._address(coil_field), bool(value))
        else:
            raise AttributeError(f"unknown field {field!r}")

    async def _enable_remote_control(
        self, field: RegisterField[Any] | CoilField
    ) -> None:
        """Release the field's override coil (set it to 0 = remote control)."""
        if field.level_coil is None:
            return
        address = field.level_coil + field.level_coil_stride * (self._index - 1)
        await self._unit.write_coil(address, False)
