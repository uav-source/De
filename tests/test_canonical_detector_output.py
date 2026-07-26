import copy
import json

import pytest

from fastlio2_adapter.canonical_detector_output import (
    canonical_json_bytes,
    canonical_json_line,
    detector_output_checksum,
    seal_detector_output,
    validate_canonical_detector_output,
)
from fastlio2_adapter.offline_detector_determinism import (
    evaluate_frozen_observation,
)
from test_runtime_observation_v3 import v3_record


def output_record():
    return evaluate_frozen_observation(v3_record(), record_index=0)


def test_canonical_json_key_order_and_utf8_lf_are_stable():
    left = {"z": "方向", "a": 1}
    right = {"a": 1, "z": "方向"}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_json_line(left).endswith(b"\n")
    assert not canonical_json_line(left).endswith(b"\n\n")


def test_self_checksum_excludes_the_checksum_field():
    output = output_record()
    payload = dict(output)
    payload.pop("detector_output_checksum")
    assert output["detector_output_checksum"] == detector_output_checksum(output)
    payload["detector_output_checksum"] = "f" * 64
    assert detector_output_checksum(payload) == output["detector_output_checksum"]


def test_allow_nan_is_false():
    with pytest.raises(ValueError):
        canonical_json_bytes({"metric": float("nan")})


@pytest.mark.parametrize(
    "field",
    [
        "pose_gt",
        "axis_gt",
        "oracle_axis",
        "scene_label",
        "harmful_label",
        "ground_truth",
        "future_value",
        "holdout_value",
        "trajectory_error",
        "AUROC",
        "FPR",
        "Recall",
    ],
)
def test_forbidden_scientific_fields_fail(field):
    output = output_record()
    output[field] = 1
    with pytest.raises(ValueError):
        seal_detector_output(output)


def test_runtime_identity_fields_are_not_added_to_canonical_output():
    output = output_record()
    for field in (
        "created_at",
        "wall_time",
        "runtime_ns",
        "process_id",
        "hostname",
        "temporary_directory",
        "fresh_process_run_number",
    ):
        assert field not in output


def test_checksum_detects_post_seal_change():
    output = output_record()
    changed = copy.deepcopy(output)
    changed["scan_index"] += 1
    with pytest.raises(ValueError, match="checksum"):
        validate_canonical_detector_output(changed)


def test_canonical_output_is_plain_json_round_trip():
    output = output_record()
    assert json.loads(canonical_json_bytes(output)) == output
