import copy
from pathlib import Path

import pytest

from eval.measurement_pilot import (
    IntervalLockError,
    load_interval_lock,
    validate_interval_lock,
)


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "configs/real_data/mun_frl_pilot_intervals.yaml"


def test_mun_intervals_and_reference_axis_are_frozen_before_detector():
    lock = load_interval_lock(LOCK_PATH)
    assert lock["lock"]["state"] == "FROZEN_BEFORE_DETECTOR"
    assert lock["lock"]["detector_outputs_examined"] is False
    assert lock["lock"]["detector_metrics_used_for_selection"] == []
    assert len(lock["interval_lock_sha256"]) == 64
    assert {interval["label"] for interval in lock["intervals"]} >= {
        "structural_degeneracy_candidate",
        "geometry_rich_control",
    }


def test_interval_lock_fails_closed_after_detector_output_examination():
    lock = load_interval_lock(LOCK_PATH)
    lock.pop("interval_lock_sha256")
    contaminated = copy.deepcopy(lock)
    contaminated["lock"]["detector_outputs_examined"] = True
    with pytest.raises(IntervalLockError, match="examined"):
        validate_interval_lock(contaminated)


def test_reference_axis_cannot_be_derived_from_detector_eigenvector():
    lock = load_interval_lock(LOCK_PATH)
    lock.pop("interval_lock_sha256")
    contaminated = copy.deepcopy(lock)
    contaminated["intervals"][0]["reference_axis"][
        "uses_detector_eigenvector"
    ] = True
    with pytest.raises(IntervalLockError, match="eigenvectors"):
        validate_interval_lock(contaminated)

