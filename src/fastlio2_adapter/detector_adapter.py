"""Thin Day 4 mapping from read-only observations to the production detector."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from degen_detector.odi_tracker import compute_metrics_for_frame

from .detector_output_schema import (
    SCHEMA_VERSION as OUTPUT_SCHEMA_VERSION,
    RECORD_VERSION as OUTPUT_RECORD_VERSION,
    canonical_sha256,
    detector_output_payload_checksum,
    validate_readonly_detector_output,
)
from .readonly_observation_schema import validate_first_valid_observation_record


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ENTRYPOINT_FILE = "src/degen_detector/odi_tracker.py"
PRODUCTION_ENTRYPOINT_SYMBOL = "compute_metrics_for_frame"
PRODUCTION_ENTRYPOINT = (
    f"{PRODUCTION_ENTRYPOINT_FILE}::{PRODUCTION_ENTRYPOINT_SYMBOL}"
)
DETECTOR_CONFIG_PATH = "configs/detector/odi_stage2a.yaml"
DETECTOR_LOCK_PATH = (
    "artifacts/current/detector_stage2a/locked/detector_lock.json"
)
DETECTOR_RESIDUAL_INPUT_FIELD = "formal_filter_innovation_h"
MEASUREMENT_WEIGHT_REPRESENTATION = "CONSTANT_SCALAR_VARIANCE"
DETECTOR_STATE_ORDER = (
    "delta_theta_x",
    "delta_theta_y",
    "delta_theta_z",
    "delta_p_x",
    "delta_p_y",
    "delta_p_z",
)
DETECTOR_TRANSLATION_FRAME = "WORLD"
PRIOR_COVARIANCE_USED_BY_DETECTOR = False


def evaluate_readonly_observation(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate, map, call the production detector, and return schema output."""

    validate_first_valid_observation_record(record)
    if record["synthetic_only"] is not True:
        raise ValueError("Day 4 adapter accepts synthetic observations only")

    detector_input = prepare_production_detector_input(record)
    provenance = detector_input["provenance"]
    base = _base_output(record, detector_input, provenance)

    jacobian = detector_input["jacobian"]
    variance = detector_input["variance"]
    if jacobian.shape[0] < jacobian.shape[1]:
        return _finalize_output(
            base, valid=False, invalid_reason="TOO_FEW_CORRESPONDENCES"
        )
    if not (
        np.all(np.isfinite(jacobian))
        and np.all(np.isfinite(variance))
        and np.all(np.isfinite(detector_input["residual"]))
    ):
        return _finalize_output(
            base, valid=False, invalid_reason="NONFINITE_DETECTOR_INPUT"
        )

    try:
        metrics = compute_metrics_for_frame(
            jacobian,
            variance,
            detector_input["config"],
        )
    except (KeyError, TypeError, ValueError, FloatingPointError):
        return _finalize_output(
            base, valid=False, invalid_reason="DETECTOR_REJECTED"
        )

    numeric_values = [
        metrics["ODI_trans"],
        metrics["AIS_trans_normalized"],
        metrics["lambda_min_trans_normalized"],
        metrics["condition_number_trans"],
        metrics["trans_eig_1"],
        metrics["trans_eig_2"],
        metrics["trans_eig_3"],
        metrics["primary_weak_dir_x"],
        metrics["primary_weak_dir_y"],
        metrics["primary_weak_dir_z"],
        metrics["primary_eigengap_ratio"],
    ]
    if not np.all(np.isfinite(np.asarray(numeric_values, dtype=np.float64))):
        return _finalize_output(
            base, valid=False, invalid_reason="DETECTOR_OUTPUT_NONFINITE"
        )

    base.update(
        {
            "valid": True,
            "invalid_reason": "NONE",
            "odi_trans": float(metrics["ODI_trans"]),
            "ais_trans": float(metrics["AIS_trans_normalized"]),
            "lambda_min_trans": float(
                metrics["lambda_min_trans_normalized"]
            ),
            "condition_number_trans": float(
                metrics["condition_number_trans"]
            ),
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
            "primary_eigengap_ratio": float(
                metrics["primary_eigengap_ratio"]
            ),
            "primary_direction_stable": bool(
                metrics["primary_direction_stable"]
            ),
            "degeneracy_triggered": bool(metrics["degeneracy_triggered"]),
            "actionable_direction": bool(metrics["actionable_direction"]),
        }
    )
    return _seal_and_validate(base)


def prepare_production_detector_input(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Create independent arrays without reordering the Day 3 pose columns."""

    validate_first_valid_observation_record(record)
    jacobian = np.asarray(
        record["detector_pose_jacobian_rows"], dtype=np.float64
    ).copy()
    residual = np.asarray(
        record[DETECTOR_RESIDUAL_INPUT_FIELD], dtype=np.float64
    ).copy()
    geometric = np.asarray(
        record["signed_geometric_residual_pd2"], dtype=np.float64
    )
    if not np.allclose(residual, -geometric, rtol=0.0, atol=1.0e-12):
        raise ValueError("formal detector residual must equal negative pd2")
    variance = np.full(
        jacobian.shape[0],
        float(record["measurement_variance_scalar_m2"]),
        dtype=np.float64,
    )
    config, provenance = load_production_detector_contract()
    checksum_payload = {
        "jacobian": jacobian.tolist(),
        "variance": variance.tolist(),
        "residual_field": DETECTOR_RESIDUAL_INPUT_FIELD,
        "residual": residual.tolist(),
        "state_order": list(DETECTOR_STATE_ORDER),
        "translation_frame": DETECTOR_TRANSLATION_FRAME,
    }
    return {
        "jacobian": jacobian,
        "variance": variance,
        "residual": residual,
        "config": config,
        "provenance": provenance,
        "checksum": canonical_sha256(checksum_payload),
    }


def load_production_detector_contract() -> tuple[dict[str, Any], dict[str, str]]:
    source_path = ROOT / PRODUCTION_ENTRYPOINT_FILE
    config_path = ROOT / DETECTOR_CONFIG_PATH
    lock_path = ROOT / DETECTOR_LOCK_PATH
    source_sha = _file_sha256(source_path)
    config_sha = _file_sha256(config_path)
    lock_sha = _file_sha256(lock_path)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    source_hashes = lock.get("source_file_hashes", {})
    if source_hashes.get(PRODUCTION_ENTRYPOINT_FILE) != source_sha:
        raise RuntimeError("production detector source does not match frozen lock")
    if source_hashes.get(DETECTOR_CONFIG_PATH) != config_sha:
        raise RuntimeError("production detector config does not match frozen lock")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise RuntimeError("production detector config must be a mapping")
    config = dict(config)
    config["odi_trigger_threshold"] = lock["odi_trigger_threshold"]
    if float(config["primary_direction_min_eigengap_ratio"]) != float(
        lock["direction_min_eigengap_ratio"]
    ):
        raise RuntimeError("production direction setting does not match frozen lock")
    provenance = {
        "detector_metric_version": str(lock["metric_definition_version"]),
        "detector_source_sha256": source_sha,
        "detector_config_sha256": config_sha,
        "detector_lock_sha256": lock_sha,
    }
    return config, provenance


def _base_output(
    record: Mapping[str, Any],
    detector_input: Mapping[str, Any],
    provenance: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "record_version": OUTPUT_RECORD_VERSION,
        "scan_index": int(record["scan_index"]),
        "timestamp_begin": float(record["timestamp_begin"]),
        "timestamp_end": float(record["timestamp_end"]),
        "measurement_call_index": int(record["measurement_call_index"]),
        "input_observation_checksum": canonical_sha256(record),
        "detector_input_checksum": str(detector_input["checksum"]),
        "detector_output_checksum": "0" * 64,
        "detector_metric_version": provenance["detector_metric_version"],
        "detector_entrypoint": PRODUCTION_ENTRYPOINT,
        "detector_source_sha256": provenance["detector_source_sha256"],
        "detector_config_sha256": provenance["detector_config_sha256"],
        "detector_lock_sha256": provenance["detector_lock_sha256"],
        "detector_residual_input_field": DETECTOR_RESIDUAL_INPUT_FIELD,
        "measurement_weight_representation": MEASUREMENT_WEIGHT_REPRESENTATION,
        "valid_correspondence_count": int(record["valid_correspondence_count"]),
        "primary_weak_direction_frame": DETECTOR_TRANSLATION_FRAME,
        "synthetic_only": True,
    }


def _finalize_output(
    base: dict[str, Any], *, valid: bool, invalid_reason: str
) -> dict[str, Any]:
    base.update(
        {
            "valid": valid,
            "invalid_reason": invalid_reason,
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
    )
    return _seal_and_validate(base)


def _seal_and_validate(output: dict[str, Any]) -> dict[str, Any]:
    output["detector_output_checksum"] = detector_output_payload_checksum(output)
    validate_readonly_detector_output(output)
    return output


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
