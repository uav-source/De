"""Frozen-interval contracts and common Measurement pilot helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml


INTERVAL_SCHEMA_VERSION = "mun_frl_pilot_interval_lock_v1"
LOCK_STATE = "FROZEN_BEFORE_DETECTOR"
REQUIRED_LABELS = frozenset(
    {"structural_degeneracy_candidate", "geometry_rich_control"}
)
ALLOWED_SELECTION_INPUTS = frozenset(
    {
        "raw_velodyne_pointcloud_geometry",
        "position_only_navsatfix_enu_trajectory",
        "raw_scan_scene_montage",
    }
)
FORBIDDEN_SELECTION_TOKENS = (
    "odi",
    "ais",
    "schur",
    "eigenvalue",
    "weak_direction",
    "detector_output",
    "trajectory_error",
)


class IntervalLockError(ValueError):
    """The preregistered scene/axis interval contract is not trustworthy."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_interval_lock(path: Path) -> dict[str, Any]:
    lock = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_interval_lock(lock)
    lock["interval_lock_sha256"] = file_sha256(path)
    return lock


def validate_interval_lock(lock: Mapping[str, Any]) -> None:
    if lock.get("schema_version") != INTERVAL_SCHEMA_VERSION:
        raise IntervalLockError("unexpected interval lock schema")
    metadata = lock.get("lock")
    if not isinstance(metadata, Mapping):
        raise IntervalLockError("interval lock metadata is missing")
    if metadata.get("state") != LOCK_STATE:
        raise IntervalLockError("intervals were not frozen before detector execution")
    if metadata.get("selected_without_detector_outputs") is not True:
        raise IntervalLockError("selection must exclude detector outputs")
    if metadata.get("detector_outputs_examined") is not False:
        raise IntervalLockError("detector outputs were examined before interval lock")
    if metadata.get("detector_metrics_used_for_selection") != []:
        raise IntervalLockError("detector metrics contaminated interval selection")
    selection_inputs = metadata.get("selection_inputs", [])
    if not selection_inputs or not set(selection_inputs) <= ALLOWED_SELECTION_INPUTS:
        raise IntervalLockError("interval selection inputs are not allowlisted")
    lowered = " ".join(str(value).lower() for value in selection_inputs)
    if any(token in lowered for token in FORBIDDEN_SELECTION_TOKENS):
        raise IntervalLockError("detector-derived selection input is forbidden")

    intervals = lock.get("intervals")
    if not isinstance(intervals, Sequence) or len(intervals) < 2:
        raise IntervalLockError("at least two frozen intervals are required")
    labels: set[str] = set()
    previous_end: float | None = None
    for interval in sorted(intervals, key=lambda item: float(item["start_timestamp"])):
        required = (
            "interval_id",
            "start_timestamp",
            "end_timestamp",
            "label",
            "selection_basis",
            "selected_without_detector_outputs",
        )
        if any(name not in interval for name in required):
            raise IntervalLockError("frozen interval is missing required fields")
        start, end = float(interval["start_timestamp"]), float(interval["end_timestamp"])
        if not start < end:
            raise IntervalLockError("frozen interval start must precede end")
        if previous_end is not None and start < previous_end:
            raise IntervalLockError("frozen intervals must not overlap")
        previous_end = end
        if interval["selected_without_detector_outputs"] is not True:
            raise IntervalLockError("each interval must be detector-independent")
        labels.add(str(interval["label"]))
        reference = interval.get("reference_axis")
        if reference is not None:
            axis = np.asarray(reference.get("vector"), dtype=np.float64)
            if axis.shape != (3,) or not np.all(np.isfinite(axis)):
                raise IntervalLockError("reference axis must be a finite 3-vector")
            if not np.isclose(np.linalg.norm(axis), 1.0, atol=1.0e-12):
                raise IntervalLockError("reference axis must be normalized")
            if reference.get("uses_detector_eigenvector") is not False:
                raise IntervalLockError("reference axis cannot use detector eigenvectors")
            if reference.get("uses_detector_metric") is not False:
                raise IntervalLockError("reference axis cannot use detector metrics")
            if float(reference.get("angular_uncertainty_deg", -1.0)) < 0.0:
                raise IntervalLockError("reference-axis uncertainty is required")
    if not REQUIRED_LABELS <= labels:
        raise IntervalLockError("structural and control labels must both be frozen")


def interval_for_timestamp(
    timestamp: float, intervals: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    for interval in intervals:
        if float(interval["start_timestamp"]) <= timestamp <= float(
            interval["end_timestamp"]
        ):
            return interval
    return None

