import pytest

from eval.stage2_failure_day13_design import build_trial_plan, validate_trial_plan


def _seeds():
    return {
        "calibration": {"geometry": range(100, 105), "sensor": [200, 201], "process": [300, 301]},
        "evaluation": {"geometry": range(400, 410), "sensor": [500, 501], "process": [600, 601]},
    }


def test_trial_plan_is_exact_260_plus_520_clean_coherent_gross_matrix():
    rows = build_trial_plan(_seeds())
    assert len([row for row in rows if row["role"] == "calibration"]) == 260
    assert len([row for row in rows if row["role"] == "evaluation"]) == 520
    assert {row["method"] for row in rows} == {"huber_full"}
    assert all(row["stress"] == "clean" for row in rows if row["sweep"] == "open_control")


def test_missing_trial_or_historical_day11_seed_is_rejected():
    rows = list(build_trial_plan(_seeds()))
    with pytest.raises(ValueError):
        validate_trial_plan(rows[:-1], _seeds())
    changed = [dict(row) for row in rows]
    changed[0]["geometry_seed"] = 4003
    with pytest.raises(ValueError):
        validate_trial_plan(changed, _seeds())
