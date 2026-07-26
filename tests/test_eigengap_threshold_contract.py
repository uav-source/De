import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from degen_detector.weak_direction import estimate_primary_direction
from eval.interval_validity_audit import EIGENGAP_RATIO_THRESHOLD


ROOT = Path(__file__).resolve().parents[1]


def test_eigengap_ratio_uses_ascending_minimum_pair_and_greater_equal_threshold():
    # Deliberately unsorted: the minimum pair is 0 and 2, while lambda_max=100.
    at_threshold = estimate_primary_direction(
        np.asarray([100.0, 2.0, 0.0]),
        np.eye(3),
        min_eigengap_ratio=EIGENGAP_RATIO_THRESHOLD,
    )
    below = estimate_primary_direction(
        np.asarray([100.0, 1.9, 0.0]),
        np.eye(3),
        min_eigengap_ratio=EIGENGAP_RATIO_THRESHOLD,
    )
    assert at_threshold.eigengap_ratio == EIGENGAP_RATIO_THRESHOLD
    assert at_threshold.direction_stable is True
    assert below.eigengap_ratio == pytest.approx(0.019)
    assert below.direction_stable is False


def test_absolute_gap_does_not_replace_ratio_and_zero_spectrum_is_regularized():
    large_absolute_but_small_ratio = estimate_primary_direction(
        np.asarray([0.0, 1.0, 100.0]),
        np.eye(3),
        min_eigengap_ratio=EIGENGAP_RATIO_THRESHOLD,
    )
    zero = estimate_primary_direction(
        np.zeros(3),
        np.eye(3),
        min_eigengap_ratio=EIGENGAP_RATIO_THRESHOLD,
    )
    assert large_absolute_but_small_ratio.eigengap_ratio == pytest.approx(0.01)
    assert large_absolute_but_small_ratio.direction_stable is False
    assert zero.eigengap_ratio == 0.0
    assert zero.direction_stable is False


def test_nonfinite_eigenvalues_are_rejected_before_assignment():
    with pytest.raises(ValueError, match="NaN or Inf"):
        estimate_primary_direction(
            np.asarray([0.0, np.nan, 1.0]),
            np.eye(3),
            min_eigengap_ratio=EIGENGAP_RATIO_THRESHOLD,
        )


def test_eigengap_threshold_and_implementation_match_frozen_synthetic_lock():
    lock = json.loads(
        (
            ROOT
            / "artifacts/current/detector_stage2a/locked/detector_lock.json"
        ).read_text(encoding="utf-8")
    )
    config_path = ROOT / "configs/detector/odi_stage2a.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    implementation_path = ROOT / "src/degen_detector/weak_direction.py"

    assert lock["direction_min_eigengap_ratio"] == EIGENGAP_RATIO_THRESHOLD
    assert (
        config["primary_direction_min_eigengap_ratio"]
        == EIGENGAP_RATIO_THRESHOLD
    )
    assert lock["metric_definition_version"] == "detector_stage2a_v1"
    assert lock["source_file_hashes"]["src/degen_detector/weak_direction.py"] == (
        hashlib.sha256(implementation_path.read_bytes()).hexdigest()
    )
    assert lock["source_file_hashes"]["configs/detector/odi_stage2a.yaml"] == (
        hashlib.sha256(config_path.read_bytes()).hexdigest()
    )
