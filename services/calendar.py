"""Working-day calendar (docs/ai/prediction-engine.md §1).

Pure functions. Friday is the Bangladesh garment weekend; holidays are extra non-working days;
overtime days (what-if) are extra working days that override the weekend.

No Django imports — this module is part of the pure engine.
"""
from __future__ import annotations

from datetime import date, timedelta

ONE = timedelta(days=1)
FRIDAY = 4  # date.weekday(): Mon=0 ... Fri=4 ... Sun=6


def is_working_day(d: date, holidays: frozenset[date] = frozenset(), overtime: frozenset[date] = frozenset()) -> bool:
    if d in overtime:
        return True
    if d.weekday() == FRIDAY:
        return False
    if d in holidays:
        return False
    return True


def wd_between(
    a: date, b: date, holidays: frozenset[date] = frozenset(), overtime: frozenset[date] = frozenset()
) -> int:
    """Working days d with a <= d < b (half-open)."""
    n, d = 0, a
    while d < b:
        if is_working_day(d, holidays, overtime):
            n += 1
        d += ONE
    return n


def nth_wd(
    start: date, n: int, holidays: frozenset[date] = frozenset(), overtime: frozenset[date] = frozenset()
) -> date:
    """The n-th working day counting `start` as day 1 when it is a working day."""
    d, c = start, 0
    while True:
        if is_working_day(d, holidays, overtime):
            c += 1
            if c == n:
                return d
        d += ONE


def next_wd(d: date, holidays: frozenset[date] = frozenset(), overtime: frozenset[date] = frozenset()) -> date:
    d += ONE
    while not is_working_day(d, holidays, overtime):
        d += ONE
    return d


def prev_wd(d: date, holidays: frozenset[date] = frozenset(), overtime: frozenset[date] = frozenset()) -> date:
    d -= ONE
    while not is_working_day(d, holidays, overtime):
        d -= ONE
    return d
