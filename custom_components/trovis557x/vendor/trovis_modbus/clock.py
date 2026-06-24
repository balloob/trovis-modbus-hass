"""The controller's date and time, as native ``datetime`` objects."""

from __future__ import annotations

import datetime

from modbus_connection.model import raw_register

from .model import TrovisComponent
from .utils import time_from_hhmm


class Clock(TrovisComponent):
    """Controller clock, exposed as native ``date`` / ``time`` / ``datetime``."""

    _time_raw = raw_register(99, writable=True)
    _date_raw = raw_register(100, writable=True)
    _year_raw = raw_register(101, writable=True)

    @property
    def time(self) -> datetime.time | None:
        """Time of day (the controller stores it packed as HHMM)."""
        return time_from_hhmm(self._time_raw)

    @property
    def date(self) -> datetime.date | None:
        """Calendar date (the controller stores day*100+month and the year)."""
        raw = self._date_raw
        year = self._year_raw
        if not raw or not year:
            return None
        try:
            return datetime.date(year=year, month=raw % 100, day=raw // 100)
        except ValueError:
            return None

    @property
    def datetime(self) -> datetime.datetime | None:
        """Combined date and time."""
        moment = self.time
        if (day := self.date) is None or moment is None:
            return None
        return datetime.datetime.combine(day, moment)
