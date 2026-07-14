"""Immutable analysis locking and provenance hashes for Stage 1c."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import scipy


METRIC_DEFINITION_VERSION = "stage1c_v1"


def calibrate_low_information_threshold(
    development_open_control_metrics: Any,
    quantile: float = 0.05,
) -> float:
    """Calibrate tau_I from development open-control frames only."""

    if not 0.0 < float(quantile) < 1.0:
        raise ValueError("quantile must be strictly between zero and one")
    if isinstance(development_open_control_metrics, np.ndarray) and development_open_control_metrics.dtype.names:
        values = np.asarray(development_open_control_metrics["axis_information_normalized"], dtype=float)
    else:
        values = np.asarray(
            [
                float(row["axis_information_normalized"])
                if isinstance(row, Mapping)
                else float(row)
                for row in development_open_control_metrics
            ],
            dtype=float,
        )
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("development open-control calibration has no finite frames")
    return float(np.quantile(values, float(quantile)))


def stage1c_source_paths(root: Path) -> List[Path]:
    root = Path(root).resolve()
    return [
        root / "src/degen_detector",
        root / "src/minibench",
        root / "src/eval",
        root / "tests",
        root / "scripts/28_run_metric_redesign_stage1c.py",
        root / "scripts/29_run_verified_pytest.py",
        root / "configs/redesign/stage1c_common.yaml",
        root / "configs/redesign/stage1c_development.yaml",
        root / "configs/redesign/stage1c_test.yaml",
        root / "configs/redesign/stage1c_quick.yaml",
        root / "configs/detector/odi_stage1c.yaml",
        root / "configs/toy_lio/motion_surrogate_stage1c.yaml",
        root / "pytest.ini",
    ]


def stage1c_config_paths(root: Path) -> List[Path]:
    root = Path(root).resolve()
    return [
        root / "configs/redesign/stage1c_common.yaml",
        root / "configs/redesign/stage1c_development.yaml",
        root / "configs/redesign/stage1c_test.yaml",
        root / "configs/redesign/stage1c_quick.yaml",
        root / "configs/detector/odi_stage1c.yaml",
        root / "configs/toy_lio/motion_surrogate_stage1c.yaml",
    ]


def compute_source_tree_hash(paths: List[Path]) -> str:
    digest, _ = compute_source_tree_snapshot(paths)
    return digest


def compute_source_tree_snapshot(paths: Sequence[Path]) -> Tuple[str, Dict[str, str]]:
    files = collect_hash_files(paths)
    common_root = Path(Path.cwd()).resolve()
    snapshot: Dict[str, str] = {}
    digest = hashlib.sha256()
    for path in files:
        try:
            name = str(path.resolve().relative_to(common_root))
        except ValueError:
            name = str(path.resolve())
        file_digest = sha256_file(path)
        snapshot[name] = file_digest
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest(), snapshot


def collect_hash_files(paths: Sequence[Path]) -> List[Path]:
    files: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(f"Stage 1c hash input is missing: {path}")
        if path.is_file():
            files.append(path)
            continue
        files.extend(
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file()
            and "__pycache__" not in candidate.parts
            and ".pytest_cache" not in candidate.parts
            and candidate.suffix not in {".pyc", ".pyo"}
        )
    return sorted(set(files), key=lambda item: str(item.resolve()))


def compute_bundle_hash(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted((Path(value) for value in paths), key=lambda item: str(item)):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def compute_directory_hash(path: Path, excluded_names: Iterable[str] = ()) -> str:
    root = Path(path)
    excluded = set(excluded_names)
    files = [
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file() and candidate.name not in excluded and "__pycache__" not in candidate.parts
    ]
    digest = hashlib.sha256()
    for candidate in sorted(files):
        name = str(candidate.relative_to(root))
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(candidate).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def changed_snapshot_files(locked: Mapping[str, str], current: Mapping[str, str]) -> List[str]:
    names = sorted(set(locked) | set(current))
    return [name for name in names if locked.get(name) != current.get(name)]


def verify_analysis_lock(root: Path, lock: Mapping[str, Any], require_clean: bool = True) -> Dict[str, Any]:
    root = Path(root).resolve()
    source_hash, source_snapshot = compute_source_tree_snapshot(stage1c_source_paths(root))
    config_hash = compute_bundle_hash(stage1c_config_paths(root))
    changed = changed_snapshot_files(lock.get("source_file_hashes", {}), source_snapshot)
    source_match = source_hash == str(lock.get("source_tree_sha256"))
    config_match = config_hash == str(lock.get("config_bundle_sha256"))
    clean = git_status_clean(root)
    if not source_match or not config_match or (require_clean and not clean):
        reasons = []
        if not source_match:
            reasons.append(f"source hash mismatch; changed files={changed}")
        if not config_match:
            reasons.append("config bundle hash mismatch")
        if require_clean and not clean:
            reasons.append("git worktree is dirty")
        raise RuntimeError("REFUSE_TEST_EXECUTION: " + "; ".join(reasons))
    return {
        "source_hash_matched": source_match,
        "config_hash_matched": config_match,
        "git_status_clean": clean,
        "changed_files": changed,
        "source_tree_sha256": source_hash,
        "config_bundle_sha256": config_hash,
    }


def build_analysis_lock(
    root: Path,
    development_run_dir: Path,
    calibration: Mapping[str, Any],
    development_manifest: Mapping[str, Any],
    development_level_medians: Mapping[str, Any],
    common: Mapping[str, Any],
    development: Mapping[str, Any],
    reserved_test: Mapping[str, Any],
) -> Dict[str, Any]:
    root = Path(root).resolve()
    source_hash, source_snapshot = compute_source_tree_snapshot(stage1c_source_paths(root))
    config_hash = compute_bundle_hash(stage1c_config_paths(root))
    metric_paths = [
        root / "src/degen_detector/whitened_info.py",
        root / "src/degen_detector/odi_tracker.py",
        root / "src/degen_detector/exposure_metrics.py",
    ]
    statistics_paths = [
        root / "src/eval/hierarchical_statistics.py",
        root / "src/eval/metric_redesign_stage1c.py",
    ]
    data_dir = root / str(development_manifest["data_run_dir"])
    tables_dir = Path(development_run_dir) / "tables"
    return {
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "primary_detector_metric": "ODI_trans",
        "primary_exposure_metric": "mean_inverse_axis_information",
        "primary_target": "mean_final_axis_error_squared",
        "secondary_targets": ["variance_final_axis_error", "mean_axis_rmse", "q95_final_axis_error_abs"],
        "expected_directions": {"ODI_trans_vs_severity": "positive", "exposure_vs_error": "positive"},
        "low_information_quantile": float(calibration["low_information_quantile"]),
        "low_axis_information_threshold": float(calibration["low_axis_information_threshold"]),
        "calibration_source": "development_open_control_only",
        "calibration_frame_count": int(calibration["calibration_frame_count"]),
        "calibration_data_hash": str(calibration["calibration_data_hash"]),
        "epsilon_rule": "fixed_exposure_epsilon",
        "epsilon_resolved": float(common["analysis"]["exposure_epsilon"]),
        "development_geometry_seeds": list(development["geometry_seeds"]),
        "development_sensor_seeds": list(development["sensor_seeds"]),
        "development_process_seeds": list(development["process_seeds"]),
        "reserved_test_geometry_seeds": list(reserved_test["geometry_seeds"]),
        "reserved_test_sensor_seeds": list(reserved_test["sensor_seeds"]),
        "reserved_test_process_seeds": list(reserved_test["process_seeds"]),
        "source_tree_sha256": source_hash,
        "source_file_hashes": source_snapshot,
        "config_bundle_sha256": config_hash,
        "config_file_hashes": {str(path.relative_to(root)): sha256_file(path) for path in stage1c_config_paths(root)},
        "metric_code_sha256": compute_source_tree_hash(metric_paths),
        "statistics_code_sha256": compute_source_tree_hash(statistics_paths),
        "development_data_sha256": compute_directory_hash(data_dir),
        "development_tables_sha256": compute_directory_hash(tables_dir),
        "development_level_medians": dict(development_level_medians),
        "development_sensor_run_count": int(development_manifest["sensor_run_count"]),
        "development_process_trial_count": int(development_manifest["process_trial_count"]),
        "development_unique_noise_sequences": int(development_manifest["unique_process_noise_sequences"]),
        "development_low_information_ratio_unique_count": int(
            development_manifest["low_information_ratio_unique_count"]
        ),
        "development_longest_low_information_duration_unique_count": int(
            development_manifest["longest_low_information_duration_unique_count"]
        ),
        "created_at": utc_now(),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "pandas_version": optional_pandas_version(),
        "platform": platform.platform(),
        "git_commit_at_lock": git_commit(root),
        "git_status_clean_at_lock": git_status_clean(root),
    }


def load_metric_csv(path: Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def git_status_clean(root: Path) -> bool:
    return subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip() == ""


def git_path_commit(root: Path, path: Path) -> str:
    """Return the commit that most recently recorded a tracked path."""

    root = Path(root).resolve()
    relative_path = Path(path).resolve().relative_to(root)
    commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", str(relative_path)],
        cwd=root,
        text=True,
    ).strip()
    if not commit:
        raise RuntimeError(f"REFUSE_TEST_EXECUTION: analysis lock is not committed: {relative_path}")
    return commit


def optional_pandas_version() -> str:
    try:
        import pandas as pd

        return str(pd.__version__)
    except ImportError:
        return "not_installed"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
