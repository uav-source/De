from pathlib import Path

import pytest

from eval.stage2_failure_day11b_lock import verify_day11a_case_lock
from eval.stage2_failure_day11b_plan import build_replay_plan, validate_replay_plan


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "results/stage2_failure_analysis/day11a_case_lock/stage2_failure_day11a_case_lock_v1/deterministic_diagnostic_case_lock.json"


def _values():
    verification = verify_day11a_case_lock(ROOT, LOCK)
    return verification, list(build_replay_plan(verification))


def test_replay_plan_is_exact_locked_eight_row_matrix():
    verification, rows = _values()
    assert len(rows) == 8
    assert [row["method"] for row in rows[:4]] == [
        "huber_full", "huber_projected_gain", "huber_full", "huber_projected_gain"
    ]
    assert rows[0]["case_id"] == "geometry_L4_g4003_s111_p6015_clean_huber_full"
    assert rows[-1]["case_id"].endswith("coherent_subhuber_slip_huber_projected_gain")
    validate_replay_plan(rows, verification)


@pytest.mark.parametrize("mutation", ["short", "long"])
def test_replay_plan_rejects_non_eight_row_matrix(mutation):
    verification, rows = _values()
    changed = rows[:-1] if mutation == "short" else rows + [dict(rows[-1])]
    with pytest.raises(ValueError, match="eight|unique"):
        validate_replay_plan(changed, verification)


def test_replay_plan_rejects_oracle_method():
    verification, rows = _values()
    rows[0] = {**rows[0], "method": "huber_oracle_projected_gain"}
    with pytest.raises(ValueError):
        validate_replay_plan(rows, verification)
