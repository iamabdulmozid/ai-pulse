"""T-06 acceptance: working-day calendar (docs/ai/prediction-engine.md §1)."""
from datetime import date

from services.calendar import is_working_day, next_wd, nth_wd, wd_between

T = date(2026, 10, 15)  # Thursday (DEMO_TODAY)
EXF = date(2026, 10, 29)
FRI = frozenset({date(2026, 10, 16), date(2026, 10, 23)})


def test_today_is_thursday():
    assert T.weekday() == 3


def test_wd_between_excludes_fridays():
    # 15..28 inclusive = 14 days; Fridays 16 & 23 excluded -> 12 working days.
    assert wd_between(T, EXF) == 12


def test_wd_between_with_overtime():
    # Adding the two Fridays as overtime days -> 14 working days (the hero what-if).
    assert wd_between(T, EXF, frozenset(), FRI) == 14


def test_wd_between_with_holiday():
    hol = frozenset({date(2026, 10, 20)})  # a Tuesday
    assert wd_between(T, EXF, hol) == 11


def test_is_working_day():
    assert is_working_day(date(2026, 10, 15)) is True
    assert is_working_day(date(2026, 10, 16)) is False  # Friday
    assert is_working_day(date(2026, 10, 16), overtime=FRI) is True
    assert is_working_day(date(2026, 10, 20), holidays=frozenset({date(2026, 10, 20)})) is False


def test_nth_wd_and_next_wd():
    assert nth_wd(T, 1) == date(2026, 10, 15)
    assert nth_wd(T, 2) == date(2026, 10, 17)  # 16 Fri skipped
    assert next_wd(date(2026, 10, 15)) == date(2026, 10, 17)
    assert next_wd(date(2026, 10, 15), overtime=FRI) == date(2026, 10, 16)
