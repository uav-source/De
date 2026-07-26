import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from eval.interval_validity_audit import (
    EIGENGAP_RATIO_THRESHOLD,
    STRUCTURAL_LABEL,
    eigengap_reliability_rows,
)


ROOT = Path(__file__).resolve().parents[1]


def _frozen_structural_inputs():
    with (
        ROOT
        / "artifacts/current/measurement_real_validation_pilot/tables/weak_direction_accuracy.csv"
    ).open(newline="", encoding="utf-8") as handle:
        weak_rows = list(csv.DictReader(handle))
    with (
        ROOT
        / "artifacts/current/measurement_real_validation_pilot/tables/frame_metrics.csv"
    ).open(newline="", encoding="utf-8") as handle:
        all_frame_rows = list(csv.DictReader(handle))
    frame_by_scan = {int(row["scan_index"]): row for row in all_frame_rows}
    frame_rows = []
    for weak in weak_rows:
        frame = dict(frame_by_scan[int(weak["scan_index"])])
        frame["interval_label"] = STRUCTURAL_LABEL
        frame_rows.append(frame)
    return weak_rows, frame_rows


def _rows_by_group(weak_rows, frame_rows):
    return {
        row["group"]: row
        for row in eigengap_reliability_rows(weak_rows, frame_rows)
    }


def test_structural_pilot_reliability_groups_are_134_and_5():
    weak_rows, frame_rows = _frozen_structural_inputs()
    assert len({int(row["scan_index"]) for row in weak_rows}) == len(weak_rows)
    assert {int(row["scan_index"]) for row in weak_rows} == {
        int(row["scan_index"]) for row in frame_rows
    }

    rows = _rows_by_group(weak_rows, frame_rows)
    reliable = rows["reliable"]
    unreliable = rows["unreliable"]
    assert (reliable["count"], unreliable["count"]) == (134, 5)
    assert reliable["median_angle_error_deg"] == pytest.approx(30.8003, abs=1e-4)
    assert unreliable["median_angle_error_deg"] == pytest.approx(28.9799, abs=1e-4)
    assert reliable["minimum_sample_warning"] is False
    assert unreliable["minimum_sample_warning"] is True


def test_frozen_reliability_assignments_and_five_reasons_are_explicit():
    weak_rows, frame_rows = _frozen_structural_inputs()
    rows = _rows_by_group(weak_rows, frame_rows)
    audit = rows["unreliable"]

    assert all(
        (row["direction_reliable"] == "True")
        == (float(row["primary_eigengap_ratio"]) >= EIGENGAP_RATIO_THRESHOLD)
        for row in frame_rows
    )
    assert audit["gap_measure"] == "primary_eigengap_ratio"
    assert audit["ratio_not_absolute_gap"] is True
    assert audit["absolute_gap_used_for_assignment"] is False
    assert audit["comparison_operator"] == ">="
    assert audit["eigenvalue_order"] == "ascending(lambda_min,lambda_mid,lambda_max)"
    assert "denominator=max(lambda_max,1e-12)" in audit["regularization"]
    assert audit["nan_primary_eigengap_ratio_count"] == 0
    assert audit["nonfinite_primary_eigengap_ratio_count"] == 0
    assert audit["assignment_mismatch_count"] == 0
    assert audit["eigenvalue_order_mismatch_count"] == 0
    assert audit["ratio_reconstruction_mismatch_count"] == 0
    assert audit["unreliable_reason_count"] == 5
    assert audit["reliability_state_nearly_constant"] is True
    assert audit["majority_group_ratio"] == pytest.approx(134 / 139)
    assert audit["reliability_validation_sufficient"] is False
    assert audit["threshold_origin_domain"] == "synthetic_development"
    assert audit["threshold_recalibrated_on_current_real_pilot"] is False

    reasons = json.loads(audit["unreliable_reasons_json"])
    assert [reason["scan_index"] for reason in reasons] == [227, 238, 280, 287, 304]
    assert all(
        reason["reason"] == "PRIMARY_EIGENGAP_RATIO_BELOW_THRESHOLD"
        and reason["primary_eigengap_ratio"] < EIGENGAP_RATIO_THRESHOLD
        and reason["predicate"] == "primary_eigengap_ratio >= threshold"
        for reason in reasons
    )


def test_nan_is_not_silently_grouped_and_assignment_mismatch_is_reported():
    weak_rows, frame_rows = _frozen_structural_inputs()
    nan_rows = deepcopy(frame_rows)
    nan_rows[0]["primary_eigengap_ratio"] = float("nan")
    nan_rows[0]["direction_reliable"] = "True"
    nan_audit = _rows_by_group(weak_rows, nan_rows)["reliable"]
    assert nan_audit["nan_primary_eigengap_ratio_count"] == 1
    assert nan_audit["nonfinite_primary_eigengap_ratio_count"] == 1
    assert nan_audit["nonfinite_classified_reliable_count"] == 1
    assert nan_audit["count"] == 133

    mismatch_rows = deepcopy(frame_rows)
    mismatch_rows[0]["direction_reliable"] = (
        "False" if mismatch_rows[0]["direction_reliable"] == "True" else "True"
    )
    mismatch_audit = _rows_by_group(weak_rows, mismatch_rows)["reliable"]
    assert mismatch_audit["assignment_mismatch_count"] == 1
