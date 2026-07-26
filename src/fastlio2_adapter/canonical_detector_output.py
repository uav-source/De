"""Canonical frozen-observation detector output encoding and validation."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_SCHEMA_PATH = (
    ROOT / "schemas/harmful_bias/readonly_detector_output_v3.schema.json"
)
SCHEMA_VERSION = "readonly_detector_output_v3"
RECORD_VERSION = "readonly_detector_output_v3"
RECORD_SOURCE = "FROZEN_REAL_OBSERVATION"
SCHEMA_RECORD_SOURCE = "FASTLIO2_RUNTIME_COMPACT_BINARY"
CANONICAL_JSON_SPEC_VERSION = "canonical-json-sort-keys-utf8-lf-v1"

FORBIDDEN_FIELD_TOKENS = (
    "pose_gt",
    "axis_gt",
    "oracle_axis",
    "scene_label",
    "harmful_label",
    "ground_truth",
    "future",
    "holdout",
    "trajectory_error",
    "auroc",
    "auprc",
    "fpr",
    "recall",
    "candidate_offsets",
    "candidate_costs",
    "imu_conflict",
)

REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "record_version",
        "record_source",
        "run_id",
        "sequence_id",
        "detector_execution_mode",
        "record_index",
        "scan_index",
        "timestamp_begin",
        "timestamp_end",
        "measurement_call_index",
        "input_observation_checksum",
        "detector_input_checksum",
        "detector_output_checksum",
        "detector_metric_version",
        "detector_entrypoint",
        "detector_source_sha256",
        "detector_config_sha256",
        "detector_lock_sha256",
        "detector_residual_input_field",
        "measurement_weight_representation",
        "valid_correspondence_count",
        "valid",
        "invalid_reason",
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "translation_eigenvalues_ascending",
        "primary_weak_direction",
        "primary_weak_direction_frame",
        "primary_eigengap_ratio",
        "primary_direction_stable",
        "degeneracy_triggered",
        "actionable_direction",
        "synthetic_only",
    }
)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the exact canonical JSON encoding used by this task."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_line(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def detector_output_checksum(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload.pop("detector_output_checksum", None)
    return canonical_sha256(payload)


def seal_detector_output(record: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(record)
    output["detector_output_checksum"] = detector_output_checksum(output)
    validate_canonical_detector_output(output)
    return output


def forbidden_field_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            name = str(raw_name)
            lowered = name.lower()
            if any(token in lowered for token in FORBIDDEN_FIELD_TOKENS):
                found.append(f"{path}.{name}")
            found.extend(forbidden_field_paths(child, f"{path}.{name}"))
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, child in enumerate(value):
            found.extend(forbidden_field_paths(child, f"{path}[{index}]"))
    return found


def validate_canonical_detector_output(record: Mapping[str, Any]) -> None:
    """Validate the frozen-source extension without changing the reused schema."""

    if not isinstance(record, Mapping):
        raise ValueError("canonical detector output must be a mapping")
    missing = sorted(REQUIRED_FIELDS - set(record))
    if missing:
        raise ValueError(f"canonical detector output missing fields: {missing}")
    forbidden = forbidden_field_paths(record)
    if forbidden:
        raise ValueError(f"canonical detector output has forbidden fields: {forbidden}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unexpected canonical output schema_version")
    if record["record_version"] != RECORD_VERSION:
        raise ValueError("unexpected canonical output record_version")
    if record["record_source"] != RECORD_SOURCE:
        raise ValueError("unexpected canonical output record_source")
    if record["synthetic_only"] is not False:
        raise ValueError("canonical output synthetic_only must be false")
    record_index = record["record_index"]
    if (
        isinstance(record_index, bool)
        or not isinstance(record_index, int)
        or record_index < 0
    ):
        raise ValueError("record_index must be a nonnegative integer")
    if record["detector_output_checksum"] != detector_output_checksum(record):
        raise ValueError("canonical detector output checksum mismatch")
    _validate_numbers(record)

    schema = json.loads(OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_view = dict(record)
    schema_view["record_source"] = SCHEMA_RECORD_SOURCE
    Draft202012Validator(schema).validate(schema_view)


def _validate_numbers(record: Mapping[str, Any]) -> None:
    numeric_fields = (
        "timestamp_begin",
        "timestamp_end",
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "primary_eigengap_ratio",
    )
    for name in numeric_fields:
        value = record[name]
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"{name} must be finite or null")
    if record["valid"]:
        for name in (
            "odi_trans",
            "ais_trans",
            "lambda_min_trans",
            "condition_number_trans",
            "primary_eigengap_ratio",
        ):
            if record[name] is None:
                raise ValueError(f"valid output requires {name}")
        for name in (
            "translation_eigenvalues_ascending",
            "primary_weak_direction",
        ):
            values = record[name]
            if (
                not isinstance(values, Sequence)
                or isinstance(values, (str, bytes, bytearray))
                or len(values) != 3
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    for value in values
                )
            ):
                raise ValueError(f"valid output requires finite {name}")
    else:
        for name in (
            "odi_trans",
            "ais_trans",
            "lambda_min_trans",
            "condition_number_trans",
            "translation_eigenvalues_ascending",
            "primary_weak_direction",
            "primary_eigengap_ratio",
        ):
            if record[name] is not None:
                raise ValueError(f"invalid output requires {name}=null")
