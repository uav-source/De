"""Canonical offline diagnostic stream from the frozen production entrypoint."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator

from degen_detector.odi_tracker import compute_metrics_for_frame

from .canonical_detector_output import canonical_sha256, forbidden_field_paths
from .detector_adapter import PRODUCTION_ENTRYPOINT
from .offline_detector_determinism import prepare_offline_detector_input


SCHEMA_VERSION = "offline_direct_production_metrics_v1"
RECORD_SOURCE = "FROZEN_REAL_OBSERVATION_DIRECT_PRODUCTION"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas/harmful_bias/offline_direct_production_metrics_v1.schema.json"
)
METRIC_FIELDS = (
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


def direct_output_checksum(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload.pop("direct_output_checksum", None)
    return canonical_sha256(payload)


def evaluate_direct_production(
    record: Mapping[str, Any],
    *,
    record_index: int,
) -> dict[str, Any]:
    prepared = prepare_offline_detector_input(record)
    jacobian = prepared["jacobian"]
    provenance = prepared["provenance"]
    base = {
        "schema_version": SCHEMA_VERSION,
        "record_source": RECORD_SOURCE,
        "record_index": int(record_index),
        "scan_index": int(record["scan_index"]),
        "timestamp_begin": float(record["timestamp_begin"]),
        "timestamp_end": float(record["timestamp_end"]),
        "measurement_call_index": int(record["measurement_call_index"]),
        "input_observation_checksum": canonical_sha256(record),
        "detector_input_checksum": str(prepared["checksum"]),
        "direct_output_checksum": "0" * 64,
        "detector_metric_version": provenance["detector_metric_version"],
        "detector_entrypoint": PRODUCTION_ENTRYPOINT,
        "detector_source_sha256": provenance["detector_source_sha256"],
        "detector_config_sha256": provenance["detector_config_sha256"],
        "detector_lock_sha256": provenance["detector_lock_sha256"],
        "jacobian_row_count": int(jacobian.shape[0]),
        "jacobian_column_count": int(jacobian.shape[1]),
        "valid_correspondence_count": int(record["valid_correspondence_count"]),
    }
    try:
        metrics = compute_metrics_for_frame(
            jacobian,
            prepared["variance"],
            prepared["config"],
        )
        values = {
            "odi_trans": float(metrics["ODI_trans"]),
            "ais_trans": float(metrics["AIS_trans_normalized"]),
            "lambda_min_trans": float(metrics["lambda_min_trans_normalized"]),
            "condition_number_trans": float(metrics["condition_number_trans"]),
            "translation_eigenvalues_ascending": sorted(
                [
                    float(metrics["trans_eig_1"]),
                    float(metrics["trans_eig_2"]),
                    float(metrics["trans_eig_3"]),
                ]
            ),
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
        numeric = [
            values["odi_trans"],
            values["ais_trans"],
            values["lambda_min_trans"],
            values["condition_number_trans"],
            *values["translation_eigenvalues_ascending"],
            *values["primary_weak_direction"],
            values["primary_eigengap_ratio"],
        ]
        if not np.all(np.isfinite(np.asarray(numeric, dtype=np.float64))):
            output = _invalid_output(base, "DETECTOR_OUTPUT_NONFINITE")
        else:
            output = {
                **base,
                "valid": True,
                "invalid_reason": "NONE",
                **values,
            }
    except (KeyError, TypeError, ValueError, FloatingPointError):
        output = _invalid_output(base, "PRODUCTION_DETECTOR_EXCEPTION")
    output["direct_output_checksum"] = direct_output_checksum(output)
    validate_direct_production_output(output)
    return output


def validate_direct_production_output(record: Mapping[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(record)
    forbidden = forbidden_field_paths(record)
    if forbidden:
        raise ValueError(f"direct diagnostic contains forbidden fields: {forbidden}")
    if record["direct_output_checksum"] != direct_output_checksum(record):
        raise ValueError("direct diagnostic checksum mismatch")
    if record["valid"]:
        if record["invalid_reason"] != "NONE":
            raise ValueError("valid direct output must use invalid_reason=NONE")
        for name in METRIC_FIELDS:
            value = record[name]
            if isinstance(value, bool):
                continue
            values = value if _is_sequence(value) else [value]
            if any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(float(item))
                for item in values
            ):
                raise ValueError(f"direct diagnostic field is not finite: {name}")
    else:
        for name in METRIC_FIELDS[:7]:
            if record[name] is not None:
                raise ValueError(f"invalid direct output requires {name}=null")
        for name in METRIC_FIELDS[7:]:
            if record[name] is not False:
                raise ValueError(f"invalid direct output requires {name}=false")


def _invalid_output(base: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        **base,
        "valid": False,
        "invalid_reason": reason,
        "odi_trans": None,
        "ais_trans": None,
        "lambda_min_trans": None,
        "condition_number_trans": None,
        "translation_eigenvalues_ascending": None,
        "primary_weak_direction": None,
        "primary_eigengap_ratio": None,
        "primary_direction_stable": False,
        "degeneracy_triggered": False,
        "actionable_direction": False,
    }


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )
