import inspect

import numpy as np
import pytest

from fastlio2_adapter.offline_detector_determinism import (
    DETECTOR_RESIDUAL_USED,
    PRIOR_COVARIANCE_USED_BY_DETECTOR,
    evaluate_frozen_observation,
    prepare_offline_detector_input,
)
from test_runtime_observation_v3 import v3_record


def test_offline_adapter_keeps_jacobian_order_and_float64():
    record = v3_record()
    prepared = prepare_offline_detector_input(record)
    assert prepared["jacobian"].dtype == np.float64
    assert np.array_equal(
        prepared["jacobian"],
        np.asarray(record["detector_pose_jacobian_rows"], dtype=np.float64),
    )


def test_scalar_variance_is_expanded_once_to_all_rows():
    record = v3_record()
    prepared = prepare_offline_detector_input(record)
    assert prepared["variance"].dtype == np.float64
    assert prepared["variance"].shape == (record["valid_correspondence_count"],)
    assert np.array_equal(
        prepared["variance"],
        np.full(
            record["valid_correspondence_count"],
            record["measurement_variance_scalar_m2"],
            dtype=np.float64,
        ),
    )


def test_prior_covariance_and_residual_are_not_detector_math_inputs():
    assert PRIOR_COVARIANCE_USED_BY_DETECTOR is False
    assert DETECTOR_RESIDUAL_USED is False
    source = inspect.getsource(
        __import__(
            "fastlio2_adapter.offline_detector_determinism",
            fromlist=["direct_production_metrics"],
        ).direct_production_metrics
    )
    assert "prior_covariance" not in source
    assert "residual" not in source


def test_adapter_source_does_not_copy_detector_linear_algebra():
    module = __import__(
        "fastlio2_adapter.offline_detector_determinism", fromlist=["x"]
    )
    source = inspect.getsource(module)
    for token in (
        "np.linalg.eig(",
        "np.linalg.eigh(",
        "np.linalg.svd(",
        "np.linalg.det(",
        "np.linalg.cond(",
        "def compute_schur",
        "def compute_odi",
        "def compute_ais",
    ):
        assert token not in source


def test_invalid_detector_result_still_emits_one_output():
    record = v3_record()
    record["detector_pose_jacobian_rows"] = record[
        "detector_pose_jacobian_rows"
    ][:3]
    record["formal_filter_innovation_h"] = record[
        "formal_filter_innovation_h"
    ][:3]
    record["valid_correspondence_count"] = 3
    output = evaluate_frozen_observation(record, record_index=4)
    assert output["record_index"] == 4
    assert output["valid"] is False
    assert output["invalid_reason"] == "TOO_FEW_CORRESPONDENCES"


def test_nonpositive_variance_fails_observation_validation():
    record = v3_record()
    record["measurement_variance_scalar_m2"] = 0.0
    with pytest.raises(ValueError):
        prepare_offline_detector_input(record)
