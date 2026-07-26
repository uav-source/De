import csv
import json
from copy import deepcopy
from pathlib import Path

import yaml

from degen_detector.odi_tracker import evaluate_trigger_direction_state
from eval.interval_validity_audit import (
    ODI_METRIC_DEFINITION_VERSION,
    ODI_TRIGGER_CALIBRATION_FRAME_COUNT,
    ODI_TRIGGER_CONTROL_QUANTILE,
    ODI_TRIGGER_THRESHOLD,
    trigger_contract_rows,
)


ROOT = Path(__file__).resolve().parents[1]


def _frozen_frame_rows():
    path = (
        ROOT
        / "artifacts/current/measurement_real_validation_pilot/tables/frame_metrics.csv"
    )
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    interval_lock = yaml.safe_load(
        (ROOT / "configs/real_data/mun_frl_pilot_intervals.yaml").read_text(
            encoding="utf-8"
        )
    )
    for row in rows:
        timestamp = float(row["timestamp"])
        row["interval_label"] = ""
        for interval in interval_lock["intervals"]:
            if (
                float(interval["start_timestamp"])
                <= timestamp
                <= float(interval["end_timestamp"])
            ):
                row["interval_label"] = interval["label"]
                break
    return rows


def _rows_by_subset(rows):
    return {row["subset"]: row for row in trigger_contract_rows(rows)}


def test_trigger_is_high_odi_greater_equal_frozen_threshold():
    assert ODI_TRIGGER_THRESHOLD == 0.035199792993590634
    assert evaluate_trigger_direction_state(
        ODI_TRIGGER_THRESHOLD, ODI_TRIGGER_THRESHOLD, False
    ) == (True, False)
    assert evaluate_trigger_direction_state(
        ODI_TRIGGER_THRESHOLD - 1e-12, ODI_TRIGGER_THRESHOLD, True
    ) == (False, False)


def test_missing_threshold_positive_infinity_never_triggers():
    assert evaluate_trigger_direction_state(1.0, float("inf"), True) == (
        False,
        False,
    )


def test_frozen_trigger_rows_match_predicate_and_verified_stage2a_contract():
    rows = _rows_by_subset(_frozen_frame_rows())
    valid = rows["all_detector_valid"]
    control = rows["control_frozen_interval"]
    invalid = rows["invalid_lifecycle_frames"]

    assert (valid["count"], valid["trigger_count"]) == (1719, 1719)
    assert (control["count"], control["trigger_count"]) == (139, 139)
    assert valid["trigger_assignment_mismatch_total"] == 0
    assert invalid["count"] == 3
    assert invalid["invalid_trigger_count"] == 0
    assert invalid["invalid_treated_as_trigger"] is False

    assert valid["predicate"] == "ODI_trans >= threshold"
    assert valid["comparison_operator"] == ">="
    assert valid["detector_metric_version"] == ODI_METRIC_DEFINITION_VERSION
    assert valid["metric_version_matches_threshold"] is True
    assert valid["calibration_frame_count"] == ODI_TRIGGER_CALIBRATION_FRAME_COUNT
    assert valid["trigger_control_quantile"] == ODI_TRIGGER_CONTROL_QUANTILE
    assert valid["calibration_source"] == "development_open_control_only"
    assert valid["old_stage_lock_loaded"] is False
    assert valid["default_infinity_fallback_used"] is False
    assert valid["missing_threshold_triggers"] is False
    assert valid["config_field_conflict"] is False
    assert valid["detector_source_hash_verified"] is True
    assert valid["detector_config_hash_verified"] is True
    assert valid["lock_copy_hash_verified"] is True
    assert valid["hash_verification_passed"] is True
    assert valid["trigger_implementation_bug_confirmed"] is False

    threshold_fields = json.loads(valid["threshold_field_values_json"])
    assert set(threshold_fields.values()) == {ODI_TRIGGER_THRESHOLD}
    assert set(valid["loaded_lock_sha256"]) <= set("0123456789abcdef")
    assert len(valid["loaded_lock_sha256"]) == 64


def test_trigger_audit_exposes_assignment_and_contract_mismatches():
    frame_rows = _frozen_frame_rows()
    corrupted = deepcopy(frame_rows)
    first_valid = next(row for row in corrupted if row["detector_valid"] == "True")
    first_valid["degeneracy_triggered"] = "False"
    rows = _rows_by_subset(corrupted)
    assert rows["all_detector_valid"]["trigger_assignment_mismatch_total"] == 1
    assert rows["all_detector_valid"]["trigger_implementation_bug_confirmed"] is True

    conflict = trigger_contract_rows(
        frame_rows,
        contract_evidence={
            "threshold_fields": {
                "odi_trigger_threshold": ODI_TRIGGER_THRESHOLD,
                "legacy_odi_threshold": 0.5,
            }
        },
    )[0]
    assert conflict["config_field_conflict"] is True
    assert conflict["config_field_conflict_count"] == 1
    assert conflict["conflicting_threshold_fields"] == "legacy_odi_threshold"
    assert conflict["trigger_implementation_bug_confirmed"] is True
