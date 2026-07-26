import numpy as np
import pytest

from capture_range.capture_radius import build_direction_recovery_curve
from capture_range.types import PerturbationSpec


def zero_spec(direction_id: str, side: int) -> PerturbationSpec:
    return PerturbationSpec(
        perturbation_type="translation",
        direction=np.array([1.0, 0.0, 0.0]),
        signed_amplitude=0.0,
        repeat_index=0,
        seed=1,
        direction_id=direction_id,
        signed_side=side,
    )


def test_zero_amplitude_requires_explicit_identity_and_side():
    with pytest.raises(ValueError, match="signed_side"):
        PerturbationSpec("translation", np.array([1.0, 0.0, 0.0]), 0.0, 0, 1)
    with pytest.raises(ValueError, match="direction_id"):
        PerturbationSpec(
            "translation", np.array([1.0, 0.0, 0.0]), 0.0, 0, 1, signed_side=1
        )


def test_positive_and_negative_zero_trials_have_distinct_group_keys():
    positive = zero_spec("translation_x_positive", 1)
    negative = zero_spec("translation_x_negative", -1)
    assert positive.direction_group_key != negative.direction_group_key
    assert positive.signed_side == 1
    assert negative.signed_side == -1


def test_curve_preserves_signed_physical_direction_and_separate_identity():
    common = {
        "direction": [1.0, 0.0, 0.0],
        "amplitudes": [0.0, 0.1],
        "successful_trials": [3, 1],
        "total_trials": [3, 3],
        "perturbation_type": "translation",
    }
    positive = build_direction_recovery_curve(
        direction_id="translation_x_positive", signed_side=1, **common
    )
    negative = build_direction_recovery_curve(
        direction_id="translation_x_negative", signed_side=-1, **common
    )
    assert np.array_equal(positive.direction, [1.0, 0.0, 0.0])
    assert np.array_equal(negative.direction, [-1.0, 0.0, 0.0])
    assert positive.direction_group_key != negative.direction_group_key
