"""Thin offline use of the frozen runtime production-detector adapter."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from degen_detector.odi_tracker import compute_metrics_for_frame

from .canonical_detector_output import (
    RECORD_SOURCE,
    canonical_sha256,
    seal_detector_output,
    validate_canonical_detector_output,
)
from .detector_adapter import (
    DETECTOR_CONFIG_PATH,
    DETECTOR_LOCK_PATH,
    DETECTOR_STATE_ORDER,
    MEASUREMENT_WEIGHT_REPRESENTATION,
    PRODUCTION_ENTRYPOINT,
    PRODUCTION_ENTRYPOINT_FILE,
    PRODUCTION_ENTRYPOINT_SYMBOL,
    _prepare_production_detector_input_core,
)
from .frozen_observation import (
    BINARY_MAGIC,
    BINARY_VERSION,
    load_existing_converter,
    sha256_file,
    validate_freeze_manifest,
)
from .runtime_detector_adapter_v3 import (
    evaluate_runtime_observation_v3,
    validate_runtime_detector_output_v3,
)
from .runtime_observation_v3 import validate_runtime_observation_v3


EXPECTED_FROZEN_ARCHIVE_SHA256 = (
    "f68c9671e0058644b86fd1602b44b4a19ee35714e523cc10e1261650d538aca8"
)
EXPECTED_CORE_BINARY_SHA256 = (
    "d7f218068868985eee7ff01a8b7d1ce3467711d088e8c00b6c5de04ff0c120f3"
)
EXPECTED_RECORD_INDEX_SHA256 = (
    "6b68a349c9230885ae6a5ad1d71e97ecd2db93d93afb4a9902e18d3288f81443"
)
EXPECTED_RECORD_COUNT = 487
EXPECTED_SOURCE_SHA256 = (
    "c515e5321e569ed074ae1c4f33563e73a82775800f20197612c2816086676d17"
)
EXPECTED_CONFIG_SHA256 = (
    "665c3df8f794841ac5f3afe97e77f9993aaae2feaf3510043ecff6646acf2398"
)
EXPECTED_LOCK_SHA256 = (
    "075f14217f5e9c782bc1ab4051e6533f34d4932399c7f4b8cbc60a03d62fe358"
)
EXPECTED_METRIC_VERSION = "detector_stage2a_v1"
EXPECTED_OBSERVATION_SCHEMA_SHA256 = (
    "f1ec0d8f7af242e087f3ca8c3365d3950afb58733d8b2d05c99825d745d98909"
)
EXPECTED_OUTPUT_SCHEMA_SHA256 = (
    "cc012c579a25820d1e4185a9300bf1903ab92b871cf6fa0b45f98664ca5ba445"
)
DETECTOR_RESIDUAL_USED = False
PRIOR_COVARIANCE_USED_BY_DETECTOR = False
DIRECT_EQUIVALENCE_TOLERANCE = 1.0e-12

DIRECT_FIELDS = (
    "odi_trans",
    "ais_trans",
    "lambda_min_trans",
    "condition_number_trans",
    "translation_eigenvalues_ascending",
    "primary_weak_direction",
    "primary_eigengap_ratio",
    "primary_direction_stable",
    "degeneracy_triggered",
    "actionable_direction",
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha256(root: Path) -> str:
    rows = []
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        rows.append(f"{file_sha256(path)}  {path.relative_to(root).as_posix()}\n")
    return hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()


def verify_internal_sha256s(root: Path) -> dict[str, Any]:
    checksum_file = root / "SHA256SUMS"
    checked = 0
    failures: list[str] = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        digest, raw_path = line.split(maxsplit=1)
        relative = raw_path.lstrip("*")
        candidate = (root / relative).resolve()
        if root.resolve() not in candidate.parents:
            failures.append(relative)
            continue
        checked += 1
        if not candidate.is_file() or file_sha256(candidate) != digest:
            failures.append(relative)
    if failures:
        raise ValueError(f"frozen internal SHA failures: {failures}")
    return {"checked_file_count": checked, "hash_failure_count": 0}


def validate_frozen_root(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / "FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    validate_freeze_manifest(manifest)
    if manifest["FROZEN_REAL_OBSERVATION_RECORD_PASS"] is not True:
        raise ValueError("frozen record authorization is false")
    if manifest["OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED"] is not True:
        raise ValueError("offline detector determinism is not authorized")
    if manifest["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is not False:
        raise ValueError("Day 6 must remain unauthorized")
    if manifest["scientific_label_status"] != "UNVERIFIED":
        raise ValueError("frozen scientific label status changed")
    if int(manifest["observation_record_count"]) != EXPECTED_RECORD_COUNT:
        raise ValueError("unexpected frozen record count")
    if manifest["binary_sha256"] != EXPECTED_CORE_BINARY_SHA256:
        raise ValueError("freeze manifest binary SHA mismatch")
    if manifest["record_index_sha256"] != EXPECTED_RECORD_INDEX_SHA256:
        raise ValueError("freeze manifest index SHA mismatch")

    binary = root / "binary/observation_records_v3.bin"
    index = root / "index/record_index.csv"
    schema = root / "schema/readonly_observation_v3.schema.json"
    if sha256_file(binary) != EXPECTED_CORE_BINARY_SHA256:
        raise ValueError("core observation binary SHA mismatch")
    if sha256_file(index) != EXPECTED_RECORD_INDEX_SHA256:
        raise ValueError("record index SHA mismatch")
    if sha256_file(schema) != EXPECTED_OBSERVATION_SCHEMA_SHA256:
        raise ValueError("frozen observation schema SHA mismatch")

    schema_summary = json.loads(
        (root / "index/schema_validation_summary.json").read_text(encoding="utf-8")
    )
    no_gt = json.loads((root / "NO_GT_AUDIT.json").read_text(encoding="utf-8"))
    if (
        schema_summary.get("schema_validation_pass") is not True
        or int(schema_summary.get("schema_accepted_record_count", -1))
        != EXPECTED_RECORD_COUNT
        or int(schema_summary.get("schema_rejected_record_count", -1)) != 0
    ):
        raise ValueError("frozen schema summary failed")
    if (
        no_gt.get("no_gt_pass") is not True
        or int(no_gt.get("gt_topic_consumed_count", -1)) != 0
        or int(no_gt.get("forbidden_field_count", -1)) != 0
    ):
        raise ValueError("frozen no-GT summary failed")
    return {
        "manifest": manifest,
        "internal_hash_verification": verify_internal_sha256s(root),
        "core_binary_sha256": sha256_file(binary),
        "record_index_sha256": sha256_file(index),
        "observation_schema_sha256": sha256_file(schema),
        "schema_rejected_record_count": 0,
        "gt_topic_consumed_count": 0,
        "forbidden_field_count": 0,
    }


def load_frozen_records(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    identity = validate_frozen_root(root)
    converter = load_existing_converter()
    framed, integrity = converter.read_framed_binary(
        root / "binary/observation_records_v3.bin",
        magic=BINARY_MAGIC,
        version=BINARY_VERSION,
    )
    if len(framed) != EXPECTED_RECORD_COUNT:
        raise ValueError("binary input record count is not 487")
    records = [converter.decode_observation_record(item) for item in framed]
    with (root / "index/record_index.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != EXPECTED_RECORD_COUNT:
        raise ValueError("record index row count is not 487")
    previous_scan: int | None = None
    for expected, (record, row) in enumerate(zip(records, rows)):
        validate_runtime_observation_v3(record)
        if int(row["record_index"]) != expected:
            raise ValueError("record order changed")
        if int(row["scan_index"]) != int(record["scan_index"]):
            raise ValueError("record index scan mismatch")
        if int(row["measurement_call_index"]) != int(
            record["measurement_call_index"]
        ):
            raise ValueError("record index measurement call mismatch")
        if int(row["binary_record_checksum"]) != int(
            record["binary_record_checksum"]
        ):
            raise ValueError("record index checksum mismatch")
        scan = int(record["scan_index"])
        if previous_scan is not None and scan <= previous_scan:
            raise ValueError("scan order changed")
        previous_scan = scan
    identity["binary_integrity"] = integrity
    identity["input_record_count"] = len(records)
    return records, identity


def input_component_identity(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "input_observation_checksum": canonical_sha256(record),
        "detector_pose_jacobian_rows_checksum": canonical_sha256(
            record["detector_pose_jacobian_rows"]
        ),
        "formal_filter_innovation_h_checksum": canonical_sha256(
            record["formal_filter_innovation_h"]
        ),
        "prior_covariance_checksum": canonical_sha256(
            {
                "raw": record["prior_covariance_detector_order_raw"],
                "symmetric": record["prior_covariance_detector_order_symmetric"],
            }
        ),
        "measurement_variance_scalar_m2": float(
            record["measurement_variance_scalar_m2"]
        ),
        "valid_correspondence_count": int(record["valid_correspondence_count"]),
    }


def prepare_offline_detector_input(record: Mapping[str, Any]) -> dict[str, Any]:
    validate_runtime_observation_v3(record)
    prepared = _prepare_production_detector_input_core(record)
    prepared["jacobian"] = np.asarray(prepared["jacobian"], dtype=np.float64)
    prepared["variance"] = np.asarray(prepared["variance"], dtype=np.float64)
    prepared["checksum"] = canonical_sha256(
        {
            "jacobian": prepared["jacobian"].tolist(),
            "variance": prepared["variance"].tolist(),
            "state_order": list(DETECTOR_STATE_ORDER),
            "measurement_weight_representation": MEASUREMENT_WEIGHT_REPRESENTATION,
            "detector_entrypoint": PRODUCTION_ENTRYPOINT,
            "detector_source_sha256": prepared["provenance"][
                "detector_source_sha256"
            ],
            "detector_config_sha256": prepared["provenance"][
                "detector_config_sha256"
            ],
            "detector_lock_sha256": prepared["provenance"]["detector_lock_sha256"],
        }
    )
    return prepared


def evaluate_frozen_observation(
    record: Mapping[str, Any], *, record_index: int
) -> dict[str, Any]:
    validate_runtime_observation_v3(record)
    runtime_output = evaluate_runtime_observation_v3(record)
    validate_runtime_detector_output_v3(runtime_output)
    detector_input = prepare_offline_detector_input(record)
    output = dict(runtime_output)
    output["record_source"] = RECORD_SOURCE
    output["record_index"] = int(record_index)
    output["detector_input_checksum"] = detector_input["checksum"]
    output = seal_detector_output(output)
    validate_canonical_detector_output(output)
    return output


def direct_production_metrics(record: Mapping[str, Any]) -> dict[str, Any]:
    prepared = prepare_offline_detector_input(record)
    metrics = compute_metrics_for_frame(
        prepared["jacobian"],
        prepared["variance"],
        prepared["config"],
    )
    return {
        "odi_trans": float(metrics["ODI_trans"]),
        "ais_trans": float(metrics["AIS_trans_normalized"]),
        "lambda_min_trans": float(metrics["lambda_min_trans_normalized"]),
        "condition_number_trans": float(metrics["condition_number_trans"]),
        "translation_eigenvalues_ascending": [
            float(metrics["trans_eig_1"]),
            float(metrics["trans_eig_2"]),
            float(metrics["trans_eig_3"]),
        ],
        "primary_weak_direction": [
            float(metrics["primary_weak_dir_x"]),
            float(metrics["primary_weak_dir_y"]),
            float(metrics["primary_weak_dir_z"]),
        ],
        "primary_eigengap_ratio": float(metrics["primary_eigengap_ratio"]),
        "primary_direction_stable": bool(metrics["primary_direction_stable"]),
        "degeneracy_triggered": bool(metrics["degeneracy_triggered"]),
        "actionable_direction": bool(metrics["actionable_direction"]),
    }


def compare_direct_production(
    output: Mapping[str, Any],
    direct: Mapping[str, Any],
    *,
    tolerance: float = DIRECT_EQUIVALENCE_TOLERANCE,
) -> tuple[bool, float, list[str]]:
    mismatches: list[str] = []
    max_error = 0.0
    for field in DIRECT_FIELDS:
        left = output[field]
        right = direct[field]
        if isinstance(left, bool) or isinstance(right, bool):
            if left is not right:
                mismatches.append(field)
            continue
        left_values = _numeric_sequence(left)
        right_values = _numeric_sequence(right)
        if len(left_values) != len(right_values):
            mismatches.append(field)
            continue
        field_error = max(
            (abs(a - b) for a, b in zip(left_values, right_values)),
            default=0.0,
        )
        max_error = max(max_error, field_error)
        if field_error > tolerance:
            mismatches.append(field)
    return not mismatches, max_error, mismatches


def detector_identity(root: Path) -> dict[str, Any]:
    source = root / PRODUCTION_ENTRYPOINT_FILE
    config = root / DETECTOR_CONFIG_PATH
    lock = root / DETECTOR_LOCK_PATH
    output_schema = root / "schemas/harmful_bias/readonly_detector_output_v3.schema.json"
    values = {
        "candidate_entrypoint_count": 1,
        "selected_entrypoint_count": 1,
        "ambiguity_count": 0,
        "entrypoint_file": PRODUCTION_ENTRYPOINT_FILE,
        "entrypoint_symbol": PRODUCTION_ENTRYPOINT_SYMBOL,
        "entrypoint_sha256": file_sha256(source),
        "config_path_alias": DETECTOR_CONFIG_PATH,
        "config_sha256": file_sha256(config),
        "lock_path_alias": DETECTOR_LOCK_PATH,
        "lock_sha256": file_sha256(lock),
        "metric_version": EXPECTED_METRIC_VERSION,
        "expected_input_state_order": list(DETECTOR_STATE_ORDER),
        "measurement_weight_representation": MEASUREMENT_WEIGHT_REPRESENTATION,
        "detector_residual_used": DETECTOR_RESIDUAL_USED,
        "prior_covariance_used_by_detector": PRIOR_COVARIANCE_USED_BY_DETECTOR,
        "output_schema_sha256": file_sha256(output_schema),
    }
    expected = {
        "entrypoint_sha256": EXPECTED_SOURCE_SHA256,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "lock_sha256": EXPECTED_LOCK_SHA256,
        "output_schema_sha256": EXPECTED_OUTPUT_SCHEMA_SHA256,
    }
    mismatches = [name for name, value in expected.items() if values[name] != value]
    if mismatches:
        raise ValueError(f"production detector identity mismatch: {mismatches}")
    return values


def evaluate_gate(facts: Mapping[str, Any]) -> dict[str, bool]:
    required = (
        "FROZEN_INPUT_IDENTITY_PASS",
        "PRODUCTION_DETECTOR_IDENTITY_PASS",
        "PRODUCTION_DETECTOR_ENTRYPOINT_CONFIRMED",
        "OBSERVATION_SCHEMA_REUSE_PASS",
        "DETECTOR_OUTPUT_SCHEMA_REUSE_PASS",
        "THIN_ADAPTER_PASS",
        "JACOBIAN_NO_DOUBLE_REORDER_PASS",
        "VARIANCE_MAPPING_PASS",
        "PRIOR_COVARIANCE_NOT_USED_PASS",
        "RESIDUAL_NOT_USED_BY_DETECTOR_CONFIRMED",
        "DIRECT_PRODUCTION_EQUIVALENCE_PASS",
        "INPUT_IMMUTABILITY_PASS",
        "OUTPUT_COUNT_COMPLETENESS_PASS",
        "OUTPUT_SCHEMA_PASS",
        "NO_GT_PASS",
        "DETECTOR_ARTIFACT_IMMUTABILITY_PASS",
        "FRESH_PROCESS_RUN_COMPLETENESS_PASS",
        "PER_RECORD_CHECKSUM_DETERMINISM_PASS",
        "CANONICAL_JSON_BYTE_DETERMINISM_PASS",
        "WHOLE_FILE_SHA_DETERMINISM_PASS",
        "DEGEN_TARGETED_TEST_PASS",
        "DEGEN_FULL_TEST_PASS",
        "DIFF_SCOPE_PASS",
    )
    gates = {name: facts.get(name) is True for name in required}
    counts_pass = all(
        int(facts.get(name, -1)) == 0
        for name in (
            "missing_output_count",
            "duplicate_output_count",
            "schema_rejected_output_count",
            "detector_exception_count",
            "input_mutation_count",
            "direct_equivalence_mismatch_count",
            "per_record_checksum_mismatch_count",
            "json_line_mismatch_count",
            "whole_file_sha_mismatch_count",
            "forbidden_field_count",
            "gt_topic_consumed_count",
        )
    )
    boundary_pass = all(
        facts.get(name) is False
        for name in (
            "roscore_run",
            "roslaunch_run",
            "rosbag_run",
            "fastlio2_run",
            "development_run",
            "holdout_run",
            "future_test_run",
            "detector_modified",
            "config_modified",
            "lock_modified",
            "threshold_modified",
            "commit_created",
            "push_performed",
        )
    )
    complete = (
        all(gates.values())
        and counts_pass
        and boundary_pass
        and int(facts.get("fresh_process_run_count", -1)) == 3
        and all(
            int(value) == EXPECTED_RECORD_COUNT
            for value in facts.get("per_run_input_count", [])
        )
        and all(
            int(value) == EXPECTED_RECORD_COUNT
            for value in facts.get("per_run_output_count", [])
        )
    )
    gates.update(
        {
            "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS": complete,
            "FALLBACK_C_PASS": complete,
            "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED": complete,
            "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
            "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED": False,
        }
    )
    return gates


def _numeric_sequence(value: Any) -> list[float]:
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [float(item) for item in value]
    return [float(value)]
