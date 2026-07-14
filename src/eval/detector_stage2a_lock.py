"""Immutable detector-only lock and source verification for Stage 2A."""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np
import scipy

from eval.analysis_lock import (
    changed_snapshot_files,
    compute_bundle_hash,
    compute_directory_hash,
    compute_source_tree_hash,
    compute_source_tree_snapshot,
    git_commit,
    git_status_clean,
)


METRIC_DEFINITION_VERSION = "detector_stage2a_v1"


def calibrate_odi_trigger_threshold(
    open_control_odi: np.ndarray,
    quantile: float = 0.95,
) -> float:
    values = np.asarray(open_control_odi, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("development Open Control ODI values are required")
    if not 0.0 < float(quantile) < 1.0:
        raise ValueError("quantile must be strictly between zero and one")
    return float(np.quantile(values, float(quantile)))


def detector_source_paths(root: Path) -> list[Path]:
    root = Path(root).resolve()
    return [
        root / "src/degen_detector",
        root / "src/minibench",
        root / "src/eval/hierarchical_statistics.py",
        root / "src/eval/synthetic_pipeline_common.py",
        root / "src/eval/detector_stage2a.py",
        root / "src/eval/detector_stage2a_lock.py",
        root / "scripts/30_run_detector_stage2a.py",
        root / "scripts/clean_workspace.py",
        root / "tests",
        *detector_config_paths(root),
        root / "pytest.ini",
    ]


def detector_config_paths(root: Path) -> list[Path]:
    root = Path(root).resolve()
    return [
        root / "configs/detector/odi_stage2a.yaml",
        root / "configs/redesign/detector_stage2a_common.yaml",
        root / "configs/redesign/detector_stage2a_development.yaml",
        root / "configs/redesign/detector_stage2a_test.yaml",
        root / "configs/redesign/detector_stage2a_quick.yaml",
    ]


def verify_detector_lock(
    root: Path,
    lock: Mapping[str, Any],
    require_clean: bool = True,
) -> Dict[str, Any]:
    root = Path(root).resolve()
    source_hash, snapshot = compute_source_tree_snapshot(detector_source_paths(root))
    config_hash = compute_bundle_hash(detector_config_paths(root))
    changed = changed_snapshot_files(lock.get("source_file_hashes", {}), snapshot)
    clean = git_status_clean(root)
    source_match = source_hash == str(lock.get("source_tree_sha256"))
    config_match = config_hash == str(lock.get("config_bundle_sha256"))
    if not source_match or not config_match or (require_clean and not clean):
        reasons = []
        if not source_match:
            reasons.append(f"source hash mismatch; changed files={changed}")
        if not config_match:
            reasons.append("config hash mismatch")
        if require_clean and not clean:
            reasons.append("dirty worktree")
        raise RuntimeError("REFUSE_TEST_EXECUTION: " + "; ".join(reasons))
    if "odi_trigger_threshold" not in lock:
        raise RuntimeError("REFUSE_TEST_EXECUTION: detector threshold missing")
    return {
        "source_hash_matched": source_match,
        "config_hash_matched": config_match,
        "git_status_clean": clean,
        "changed_files": changed,
    }


def build_detector_lock(
    root: Path,
    development_run_dir: Path,
    threshold: Mapping[str, Any],
    development_manifest: Mapping[str, Any],
    common: Mapping[str, Any],
    development: Mapping[str, Any],
    reserved_test: Mapping[str, Any],
) -> Dict[str, Any]:
    root = Path(root).resolve()
    source_hash, snapshot = compute_source_tree_snapshot(detector_source_paths(root))
    config_hash = compute_bundle_hash(detector_config_paths(root))
    detector_code = [
        root / "src/degen_detector/odi_tracker.py",
        root / "src/degen_detector/weak_direction.py",
        root / "src/degen_detector/whitened_info.py",
        root / "src/minibench/nested_geometry_observations.py",
    ]
    statistics_code = [
        root / "src/eval/hierarchical_statistics.py",
        root / "src/eval/detector_stage2a.py",
    ]
    data_dir = root / str(development_manifest["data_run_dir"])
    return {
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "primary_metric": "ODI_trans",
        "trigger_control_quantile": float(threshold["trigger_control_quantile"]),
        "odi_trigger_threshold": float(threshold["odi_trigger_threshold"]),
        "direction_min_eigengap_ratio": float(
            common["analysis"]["primary_direction_min_eigengap_ratio"]
        ),
        "development_geometry_seeds": list(development["geometry_seeds"]),
        "development_sensor_seeds": list(development["sensor_seeds"]),
        "reserved_test_geometry_seeds": list(reserved_test["geometry_seeds"]),
        "reserved_test_sensor_seeds": list(reserved_test["sensor_seeds"]),
        "source_tree_sha256": source_hash,
        "source_file_hashes": snapshot,
        "config_bundle_sha256": config_hash,
        "detector_code_sha256": compute_source_tree_hash(detector_code),
        "statistics_code_sha256": compute_source_tree_hash(statistics_code),
        "development_data_sha256": compute_directory_hash(data_dir),
        "development_summary_sha256": compute_directory_hash(Path(development_run_dir) / "tables"),
        "development_sensor_run_count": int(development_manifest["sensor_run_count"]),
        "git_commit_at_lock": git_commit(root),
        "git_status_clean_at_lock": git_status_clean(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "platform": platform.platform(),
    }
