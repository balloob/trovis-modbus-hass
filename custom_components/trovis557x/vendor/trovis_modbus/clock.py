"""The controller's date and time, as native ``datetime`` objects."""

from __future__ import annotations

import datetime

from .component import Component, raw_register, time_value


class Clock(Component):
    """Controller clock. ``time`` decodes directly; ``date`` needs day + year."""

    time = time_value(99, writable=True, doc="Time of day")
    _date_raw = raw_register(100, writable=True)
    _year_raw = raw_register(101, writable=True)

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
