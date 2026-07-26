import pytest

from fastlio2_adapter.day8_final_full_window_analysis import (
    FINAL_GATE_REQUIRED,
    evaluate_final_gate,
)


def test_final_gate_requires_every_frozen_check():
    value = evaluate_final_gate(**{name: True for name in FINAL_GATE_REQUIRED})
    assert value["DAY8_FINAL_FULL_WINDOW_EXECUTION_PASS"]
    assert not value["FORMAL_IKDTREE_BUG_PROVEN"]
    assert not value["DATA_RACE_PROVEN"]
    assert not value["DAY9_AUTHORIZED"]


def test_false_check_fails_and_day9_stays_unauthorized():
    checks = {name: True for name in FINAL_GATE_REQUIRED}
    checks["four_replay_runs_complete_pass"] = False
    value = evaluate_final_gate(**checks)
    assert not value["DAY8_FINAL_FULL_WINDOW_EXECUTION_PASS"]
    assert not value["DAY9_AUTHORIZED"]


def test_missing_gate_field_is_rejected():
    checks = {name: True for name in FINAL_GATE_REQUIRED}
    checks.pop("audit_package_scope_pass")
    with pytest.raises(ValueError):
        evaluate_final_gate(**checks)
