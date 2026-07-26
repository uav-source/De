"""Minimal, read-only real-sequence detector execution and CSV retention.

The FAST-LIO2 compact observation binary is a transport boundary.  It is
decoded, evaluated with the frozen production detector, and can then be
deleted.  Measurement mode retains only scalar paper metrics unless the user
explicitly requests selected frozen observations.
"""

from __future__ import annotations

import copy
import csv
import io
import math
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from degen_detector.odi_tracker import compute_metrics_for_frame

from .detector_adapter import load_production_detector_contract
from .runtime_observation_v3 import validate_runtime_observation_v3


MODE_AUDIT = "audit_mode"
MODE_MEASUREMENT = "measurement_mode"
MEASUREMENT_SCHEMA_VERSION = "measurement_frame_metrics_v1"
REFERENCE_FIELD_TOKENS = (
    "ground_truth",
    "pose_gt",
    "axis_gt",
    "oracle",
    "navsat",
    "latitude",
    "longitude",
    "reference_position",
    "future_error",
)
TIMING_FIELDS = frozenset(
    {"capture_core_ms", "detector_core_ms", "logging_ms", "total_added_ms"}
)
MEASUREMENT_FIELDS = (
    "schema_version",
    "timestamp",
    "scan_index",
    "valid_correspondence_count",
    "residual_count",
    "ODI_trans",
    "AIS_trans",
    "lambda_min_trans",
    "lambda_mid_trans",
    "lambda_max_trans",
    "condition_number_trans",
    "lambda_min_over_lambda_max",
    "spectral_entropy_trans",
    "effective_rank_trans",
    "normalized_eigenvalue_min",
    "normalized_eigenvalue_mid",
    "normalized_eigenvalue_max",
    "primary_weak_direction_x",
    "primary_weak_direction_y",
    "primary_weak_direction_z",
    "primary_eigengap",
    "primary_eigengap_ratio",
    "direction_reliable",
    "degeneracy_triggered",
    "detector_valid",
    "invalid_reason",
    "capture_core_ms",
    "detector_core_ms",
    "logging_ms",
    "total_added_ms",
)


class MeasurementModeError(ValueError):
    """Measurement input or retained output violates the frozen contract."""


def _find_reference_fields(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            name = str(raw_name)
            lowered = name.lower()
            if any(token in lowered for token in REFERENCE_FIELD_TOKENS):
                found.append(f"{path}.{name}")
            found.extend(_find_reference_fields(child, f"{path}.{name}"))
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, child in enumerate(value):
            found.extend(_find_reference_fields(child, f"{path}[{index}]"))
    return found


def _base_row(
    observation: Mapping[str, Any], runtime: Mapping[str, Any] | None
) -> dict[str, Any]:
    capture_ms = (
        float(runtime.get("tap_capture_ns", 0)) * 1.0e-6
        if runtime is not None
        else 0.0
    )
    binary_writer_ms = (
        float(runtime.get("binary_writer_ns", 0)) * 1.0e-6
        if runtime is not None
        else 0.0
    )
    row = {field: "" for field in MEASUREMENT_FIELDS}
    row.update(
        {
            "schema_version": MEASUREMENT_SCHEMA_VERSION,
            "timestamp": float(observation["timestamp_end"]),
            "scan_index": int(observation["scan_index"]),
            "valid_correspondence_count": int(
                observation["valid_correspondence_count"]
            ),
            "residual_count": len(observation["formal_filter_innovation_h"]),
            "direction_reliable": False,
            "degeneracy_triggered": False,
            "detector_valid": False,
            "invalid_reason": "UNPROCESSED",
            "capture_core_ms": capture_ms,
            "detector_core_ms": 0.0,
            # The existing transport writer is serialization and is reported as
            # such; it is never relabelled as detector computation.
            "logging_ms": binary_writer_ms,
            "total_added_ms": capture_ms + binary_writer_ms,
        }
    )
    return row


class MeasurementModeProcessor:
    """Call the frozen production detector without access to estimator writes."""

    def __init__(self) -> None:
        self.config, self.detector_provenance = load_production_detector_contract()
        self.same_call_mutation_count = 0
        self.state_write_count = 0
        self.covariance_write_count = 0
        self.detector_feedback_count = 0
        self.reference_input_access_count = 0
        self.nonfinite_detector_output_count = 0

    def process(
        self,
        observation: Mapping[str, Any],
        runtime: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        reference_fields = _find_reference_fields(observation)
        if reference_fields:
            raise MeasurementModeError(
                f"online observation contains offline reference fields: {reference_fields}"
            )
        validate_runtime_observation_v3(observation)
        before = copy.deepcopy(observation)
        row = _base_row(observation, runtime)
        jacobian = np.asarray(
            observation["detector_pose_jacobian_rows"], dtype=np.float64
        ).copy()
        residual = np.asarray(
            observation["formal_filter_innovation_h"], dtype=np.float64
        ).copy()
        variance = np.full(
            jacobian.shape[0],
            float(observation["measurement_variance_scalar_m2"]),
            dtype=np.float64,
        )

        if jacobian.shape[0] < jacobian.shape[1]:
            row["invalid_reason"] = "TOO_FEW_CORRESPONDENCES"
            self._finish_immutability(observation, before)
            return row
        if not (
            np.all(np.isfinite(jacobian))
            and np.all(np.isfinite(residual))
            and np.all(np.isfinite(variance))
        ):
            row["invalid_reason"] = "NONFINITE_DETECTOR_INPUT"
            self._finish_immutability(observation, before)
            return row

        detector_start = time.perf_counter_ns()
        try:
            metrics = compute_metrics_for_frame(jacobian, variance, self.config)
        except (KeyError, TypeError, ValueError, FloatingPointError):
            metrics = None
        detector_ms = (time.perf_counter_ns() - detector_start) * 1.0e-6
        row["detector_core_ms"] = detector_ms
        row["total_added_ms"] = (
            float(row["capture_core_ms"])
            + detector_ms
            + float(row["logging_ms"])
        )
        if metrics is None:
            row["invalid_reason"] = "DETECTOR_REJECTED"
            self._finish_immutability(observation, before)
            return row

        eig = np.sort(
            np.asarray(
                [
                    metrics["trans_eig_1"],
                    metrics["trans_eig_2"],
                    metrics["trans_eig_3"],
                ],
                dtype=np.float64,
            )
        )
        values_to_check = np.asarray(
            [
                metrics["ODI_trans"],
                metrics["AIS_trans_normalized"],
                metrics["condition_number_trans"],
                metrics["primary_eigengap_ratio"],
                *eig,
            ],
            dtype=np.float64,
        )
        if not np.all(np.isfinite(values_to_check)):
            self.nonfinite_detector_output_count += 1
            row["invalid_reason"] = "DETECTOR_OUTPUT_NONFINITE"
            self._finish_immutability(observation, before)
            return row

        odi = float(metrics["ODI_trans"])
        effective_rank = 1.0 + (1.0 - odi) * 2.0
        spectral_entropy = math.log(effective_rank)
        eig_sum = float(np.sum(eig))
        normalized = eig / eig_sum if eig_sum > 0.0 else np.full(3, 1.0 / 3.0)
        row.update(
            {
                "ODI_trans": odi,
                "AIS_trans": float(metrics["AIS_trans_normalized"]),
                "lambda_min_trans": float(eig[0]),
                "lambda_mid_trans": float(eig[1]),
                "lambda_max_trans": float(eig[2]),
                "condition_number_trans": float(
                    metrics["condition_number_trans"]
                ),
                "lambda_min_over_lambda_max": float(
                    metrics["lambda_min_over_lambda_max"]
                ),
                "spectral_entropy_trans": spectral_entropy,
                "effective_rank_trans": effective_rank,
                "normalized_eigenvalue_min": float(normalized[0]),
                "normalized_eigenvalue_mid": float(normalized[1]),
                "normalized_eigenvalue_max": float(normalized[2]),
                "primary_weak_direction_x": float(
                    metrics["primary_weak_dir_x"]
                ),
                "primary_weak_direction_y": float(
                    metrics["primary_weak_dir_y"]
                ),
                "primary_weak_direction_z": float(
                    metrics["primary_weak_dir_z"]
                ),
                "primary_eigengap": float(eig[1] - eig[0]),
                "primary_eigengap_ratio": float(
                    metrics["primary_eigengap_ratio"]
                ),
                "direction_reliable": bool(
                    metrics["primary_direction_stable"]
                ),
                "degeneracy_triggered": bool(
                    metrics["degeneracy_triggered"]
                ),
                "detector_valid": True,
                "invalid_reason": "NONE",
            }
        )
        self._finish_immutability(observation, before)
        return row

    def _finish_immutability(
        self, observation: Mapping[str, Any], before: Mapping[str, Any]
    ) -> None:
        if observation != before:
            self.same_call_mutation_count += 1
            raise MeasurementModeError("measurement detector mutated its input")

    def audit_summary(self, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        invalid = Counter(
            str(row["invalid_reason"])
            for row in rows
            if not bool(row["detector_valid"])
        )
        return {
            "mode": MODE_MEASUREMENT,
            "frame_count": len(rows),
            "valid_detector_frame_count": sum(
                bool(row["detector_valid"]) for row in rows
            ),
            "invalid_reason_counts": dict(sorted(invalid.items())),
            "same_call_mutation_count": self.same_call_mutation_count,
            "state_write_count": self.state_write_count,
            "covariance_write_count": self.covariance_write_count,
            "detector_feedback_count": self.detector_feedback_count,
            "reference_input_access_count": self.reference_input_access_count,
            "nonfinite_detector_output_count": self.nonfinite_detector_output_count,
            "retained_field_count": len(MEASUREMENT_FIELDS),
            "large_observation_retention_default": False,
        }


def deterministic_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return scientific output fields, excluding wall-clock measurements."""

    return {key: value for key, value in row.items() if key not in TIMING_FIELDS}


def write_measurement_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write minimal rows and honestly add measured serialization/write time.

    A scratch stream is used once to obtain per-row CSV serialization cost. The
    final retained file contains those measured costs plus the C++ compact
    binary-writer time, which was already present in each row.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    for row in rows:
        buffer = io.StringIO()
        start = time.perf_counter_ns()
        writer = csv.DictWriter(buffer, fieldnames=MEASUREMENT_FIELDS)
        writer.writerow(row)
        serialized = buffer.getvalue()
        with path.parent.joinpath(".measurement_row.tmp").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            handle.write(serialized)
            handle.flush()
        measured_ms = (time.perf_counter_ns() - start) * 1.0e-6
        row["logging_ms"] = float(row["logging_ms"]) + measured_ms
        row["total_added_ms"] = (
            float(row["capture_core_ms"])
            + float(row["detector_core_ms"])
            + float(row["logging_ms"])
        )
    path.parent.joinpath(".measurement_row.tmp").unlink(missing_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def validate_measurement_row(row: Mapping[str, Any]) -> None:
    if tuple(row.keys()) != MEASUREMENT_FIELDS:
        raise MeasurementModeError("measurement row schema/order mismatch")
    if row["schema_version"] != MEASUREMENT_SCHEMA_VERSION:
        raise MeasurementModeError("measurement row schema version mismatch")
    if row["detector_valid"]:
        for field in MEASUREMENT_FIELDS:
            if field in {
                "schema_version",
                "invalid_reason",
                "direction_reliable",
                "degeneracy_triggered",
                "detector_valid",
            }:
                continue
            value = float(row[field])
            if not math.isfinite(value):
                raise MeasurementModeError(f"nonfinite measurement field: {field}")
