"""T-07/T-09 acceptance: pure engine + answer-key parity.

These tests are DB-free: they load the six sample workbooks with pandas, run the pure engine, and compare
to 00_Answer_Key.xlsx. The engine must reproduce every row and KPI within rounding.
"""
from pathlib import Path

from scripts import engine_parity

ENGINE_MODULES = [
    "services/calendar.py",
    "services/prediction/engine.py",
    "services/prediction/score.py",
    "services/prediction/whatif.py",
    "services/prediction/params.py",
    "services/prediction/aggregate.py",
]


def test_pure_service():
    """The engine must not import Django ORM/view symbols (docs/tech/architecture.md §1)."""
    root = Path(engine_parity.ROOT)
    for rel in ENGINE_MODULES:
        src = (root / rel).read_text(encoding="utf-8")
        assert "import django" not in src, f"{rel} imports django"
        assert "from django" not in src, f"{rel} imports from django"
        assert "from apps." not in src, f"{rel} imports an app (ORM)"


def test_engine_matches_answer_key():
    mismatches, missing, total = engine_parity.compare()
    assert missing == 0
    assert total == 412
    assert all(v == 0 for v in mismatches.values()), f"mismatches: {mismatches}"


def test_hero_whatif():
    assert engine_parity.check_hero_whatif() == 0


def test_kpis_match_answer_key():
    assert engine_parity.check_kpis() == 0
