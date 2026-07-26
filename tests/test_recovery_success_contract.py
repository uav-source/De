import math

import pytest

from capture_range.recovery_metrics import (
    DEFAULT_ROTATION_SUCCESS_THRESHOLD_RAD,
    DEFAULT_TRANSLATION_SUCCESS_THRESHOLD_M,
    evaluate_recovery_success,
)


def success(**overrides):
    values = {
        "translation_error_m": 0.01,
        "rotation_error_rad": math.radians(0.25),
        "solver_converged": True,
        "finite_result": True,
        "iteration_limit_not_failed": True,
    }
    values.update(overrides)
    return evaluate_recovery_success(**values)


def test_success_contract_uses_frozen_inclusive_pose_thresholds():
    assert success(
        translation_error_m=DEFAULT_TRANSLATION_SUCCESS_THRESHOLD_M,
        rotation_error_rad=DEFAULT_ROTATION_SUCCESS_THRESHOLD_RAD,
    )
    assert not success(translation_error_m=0.0200001)
    assert not success(rotation_error_rad=math.radians(0.50001))


@pytest.mark.parametrize(
    "field",
    ["solver_converged", "finite_result", "iteration_limit_not_failed"],
)
def test_every_solver_status_is_required(field):
    assert not success(**{field: False})


def test_nonfinite_error_fails_even_if_finite_flag_is_incorrectly_true():
    assert not success(translation_error_m=float("nan"))
    assert not success(rotation_error_rad=float("inf"))


def test_final_cost_cannot_drive_the_success_predicate():
    assert "final_cost" not in evaluate_recovery_success.__annotations__
    assert not success(translation_error_m=1.0)
