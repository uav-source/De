"""Day 8 quick-only pipeline for Stage 2 failure-mechanism frame logging."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np
import scipy

from eval.analysis_lock import (
    compute_directory_hash,
    compute_source_tree_hash,
    git_commit,
    git_status_clean,
    sha256_file,
)
from eval.stage2_failure_gt_metrics import evaluate_gt_frame_records
from eval.stage2_failure_logging import (
    DIRECTIONAL_INFORMATION_EPSILON,
    Stage2FailureOnlineLogger,
)
from eval.stage2_failure_schema import (
    FRAME_KEY_FIELDS,
    GT_SCHEMA_VERSION,
    ONLINE_SCHEMA_VERSION,
    frame_key,
    write_gt_csv,
    write_online_csv,
)
from eval.synthetic_pipeline_common import load_yaml, write_json
from minibench.map_lio import run_map_lio
from minibench.motion_simulator import process_noise_checksum


HISTORICAL_ARTIFACT_PATHS = (
    "artifacts/current/detector_stage2a",
    "artifacts/history/stage2b_column_scaling_no_go",
    "artifacts/current/weak_update_stage2c",
)
DAY8_FIXTURE_ID = "day8_unit_fixture_v1"


def run_stage2_failure_day8(
    root: Path,
    run_id: str,
    output_root: Path,
    overwrite: bool = False,
    config_path: Path = None,
) -> Mapping[str, Any]:
    """Run the independent Day 8 engineering fixture; never run reserved data."""

    root = Path(root).resolve()
    config_path = (
        root / "configs/stage2_failure/day8_quick.yaml"
        if config_path is None
        else Path(config_path).resolve()
    )
    config = load_yaml(config_path)
    _validate_quick_config(config)
    clean_at_start = git_status_clean(root)
    result_dir = Path(output_root).resolve() / str(run_id)
    if result_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Day 8 output already exists: {result_dir}; use --overwrite")
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)

    historical_before = _historical_hashes(root)
    observations, motion = build_day8_unit_fixture(int(config["frame_limit"]))
    detector_config = load_yaml(root / "configs/detector/odi_stage2a.yaml")
    update_config = load_yaml(root / "configs/update/stage2c_common.yaml")
    threshold = float(config["online_odi_threshold"])
    alpha = float(config["attenuation_alpha"])

    online_rows = []
    gt_rows = []
    enabled_outputs: Dict[str, Mapping[str, Any]] = {}
    disabled_outputs: Dict[str, Mapping[str, Any]] = {}
    max_trajectory_difference = 0.0
    max_covariance_difference = 0.0
    discrete_equivalence = True
    for method in config["methods"]:
        context = {
            "run_id": str(run_id),
            "sequence_id": DAY8_FIXTURE_ID,
            "sweep": "day8_quick",
            "level": "unit",
            "stress": "coherent_subhuber_fixture",
            "geometry_seed": int(config["geometry_seed"]),
            "sensor_seed": int(config["sensor_seed"]),
            "process_seed": int(config["process_seed"]),
            "method": str(method),
        }
        disabled = run_map_lio(
            observations,
            motion,
            detector_config,
            update_config,
            str(method),
            threshold,
            alpha,
        )
        logger = Stage2FailureOnlineLogger(
            context,
            float(config["directional_information_epsilon"]),
        )
        enabled = run_map_lio(
            observations,
            motion,
            detector_config,
            update_config,
            str(method),
            threshold,
            alpha,
            failure_logger=logger,
        )
        disabled_outputs[str(method)] = disabled
        enabled_outputs[str(method)] = enabled
        method_online = list(logger.records)
        method_gt = evaluate_gt_frame_records(
            method_online,
            enabled["prior_poses"],
            enabled["poses"],
            observations["pose_gt"],
            observations["axis_per_frame"],
        )
        online_rows.extend(method_online)
        gt_rows.extend(method_gt)

        max_trajectory_difference = max(
            max_trajectory_difference,
            _maximum_array_difference(disabled["prior_poses"], enabled["prior_poses"]),
            _maximum_array_difference(disabled["poses"], enabled["poses"]),
            _maximum_array_difference(disabled["applied_deltas"], enabled["applied_deltas"]),
        )
        max_covariance_difference = max(
            max_covariance_difference,
            _maximum_array_difference(disabled["covariances"], enabled["covariances"]),
        )
        discrete_equivalence = bool(
            discrete_equivalence
            and np.array_equal(disabled["detector_triggered"], enabled["detector_triggered"])
            and np.array_equal(disabled["actionable_direction"], enabled["actionable_direction"])
        )

    online_path = result_dir / "frame_diagnostics_online.csv"
    gt_path = result_dir / "frame_diagnostics_gt.csv"
    manifest_path = result_dir / "run_manifest.json"
    summary_path = result_dir / "day8_quick_summary.json"
    write_online_csv(online_path, online_rows)
    write_gt_csv(gt_path, gt_rows)

    online_keys = [frame_key(row) for row in online_rows]
    gt_keys = [frame_key(row) for row in gt_rows]
    duplicate_key_count = len(online_keys) - len(set(online_keys))
    enabled_nonfinite_violation_count = _finite_state_violation_count(enabled_outputs)
    disabled_nonfinite_violation_count = _finite_state_violation_count(disabled_outputs)
    finite_state_violation_count = (
        enabled_nonfinite_violation_count + disabled_nonfinite_violation_count
    )
    enabled_trajectory_checksum = _trajectory_checksum(enabled_outputs)
    disabled_trajectory_checksum = _trajectory_checksum(disabled_outputs)
    trajectory_checksum_match = (
        enabled_trajectory_checksum == disabled_trajectory_checksum
    )
    solver_failure_count = sum(
        int(output["solver_failure_count"]) for output in enabled_outputs.values()
    )
    historical_after = _historical_hashes(root)
    historical_unchanged = historical_before == historical_after
    logging_equivalent = bool(
        max_trajectory_difference <= 1.0e-12
        and max_covariance_difference <= 1.0e-12
        and discrete_equivalence
        and enabled_nonfinite_violation_count == 0
        and disabled_nonfinite_violation_count == 0
        and trajectory_checksum_match
    )
    row_join_valid = bool(
        len(online_rows) == len(gt_rows)
        and online_keys == gt_keys
        and duplicate_key_count == 0
    )
    invalid_direction_count = sum(
        int(not bool(row["weak_direction_valid"])) for row in online_rows
    )
    valid_innovation_count = sum(
        int(bool(row["weak_innovation_valid"])) for row in online_rows
    )
    day8_pass = bool(
        online_rows
        and clean_at_start
        and row_join_valid
        and valid_innovation_count > 0
        and solver_failure_count == 0
        and enabled_nonfinite_violation_count == 0
        and disabled_nonfinite_violation_count == 0
        and trajectory_checksum_match
        and logging_equivalent
        and historical_unchanged
    )

    summary = {
        "run_id": str(run_id),
        "DAY8_LOGGING_PASS": day8_pass,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "online_log_row_count": len(online_rows),
        "gt_log_row_count": len(gt_rows),
        "duplicate_key_count": duplicate_key_count,
        "invalid_direction_frame_count": invalid_direction_count,
        "valid_weak_innovation_frame_count": valid_innovation_count,
        "git_status_clean_at_start": clean_at_start,
        "logging_enabled_nonfinite_violation_count": enabled_nonfinite_violation_count,
        "logging_disabled_nonfinite_violation_count": disabled_nonfinite_violation_count,
        "nonfinite_violation_count": finite_state_violation_count,
        "solver_failure_count": solver_failure_count,
        "logging_on_off_max_trajectory_difference": max_trajectory_difference,
        "logging_on_off_max_covariance_difference": max_covariance_difference,
        "logging_discrete_state_equivalent": discrete_equivalence,
        "logging_trajectory_checksum_match": trajectory_checksum_match,
        "historical_artifacts_unchanged": historical_unchanged,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "gt_used_by_online_logger": False,
        "day9_window_statistics_implemented": False,
    }
    write_json(summary_path, summary)

    manifest = {
        "run_id": str(run_id),
        "task": "Stage 2 Failure-Mechanism Diagnosis — Day 8",
        "schema_versions": {
            "online": ONLINE_SCHEMA_VERSION,
            "gt": GT_SCHEMA_VERSION,
        },
        "git_branch": _git_branch(root),
        "git_commit": git_commit(root),
        "git_status_clean_at_start": clean_at_start,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_tree_sha256": compute_source_tree_hash(
            [root / "src/degen_detector", root / "src/minibench", root / "src/eval"]
        ),
        "config_sha256": sha256_file(config_path),
        "sequence_ids": [DAY8_FIXTURE_ID],
        "method_list": list(config["methods"]),
        "frame_count": int(config["frame_limit"]),
        "online_log_row_count": len(online_rows),
        "gt_log_row_count": len(gt_rows),
        "observation_checksum": _observation_checksum(observations),
        "process_noise_checksum": process_noise_checksum(dict(motion)),
        "stress_checksum": _array_mapping_checksum(
            {
                "r_list": observations["r_list"],
                "contamination_mask": observations["contamination_mask"],
            }
        ),
        "online_log_sha256": sha256_file(online_path),
        "gt_log_sha256": sha256_file(gt_path),
        "logging_enabled_trajectory_checksum": enabled_trajectory_checksum,
        "logging_disabled_trajectory_checksum": disabled_trajectory_checksum,
        "logging_trajectory_equivalent": logging_equivalent,
        "logging_on_off_max_trajectory_difference": max_trajectory_difference,
        "logging_on_off_max_covariance_difference": max_covariance_difference,
        "historical_artifact_hashes_before": historical_before,
        "historical_artifact_hashes_after": historical_after,
        "historical_artifacts_unchanged": historical_unchanged,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "gt_used_by_online_logger": False,
        "solver_failure_count": solver_failure_count,
        "logging_enabled_nonfinite_violation_count": enabled_nonfinite_violation_count,
        "logging_disabled_nonfinite_violation_count": disabled_nonfinite_violation_count,
        "nonfinite_violation_count": finite_state_violation_count,
        "duplicate_key_count": duplicate_key_count,
        "DAY8_LOGGING_PASS": day8_pass,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    write_json(manifest_path, manifest)
    return manifest


def build_day8_unit_fixture(frame_count: int = 8):
    """Create a deterministic fixture disjoint from every Development/Test seed."""

    if not 2 <= int(frame_count) <= 8:
        raise ValueError("Day 8 quick frame_count must be between 2 and 8")
    frames = int(frame_count)
    points_per_frame = 24
    rng = np.random.default_rng(80817)
    base_points = rng.uniform(-2.0, 2.0, size=(points_per_frame, 3))
    normals = []
    for index in range(points_per_frame):
        weak_component = 0.02 + 0.008 * float(index % 6)
        strong = (
            np.array([weak_component, 1.0, 0.0])
            if index % 2 == 0
            else np.array([weak_component, 0.0, 1.0])
        )
        normals.append(strong / np.linalg.norm(strong))
    normals_one = np.asarray(normals, dtype=float)

    timestamps = np.arange(frames, dtype=float) * 0.1
    poses = np.zeros((frames, 8), dtype=float)
    poses[:, 0] = timestamps
    poses[:, 1] = np.arange(frames, dtype=float) * 0.04
    poses[:, 7] = 1.0
    points = np.tile(base_points, (frames, 1, 1))
    normals_all = np.tile(normals_one, (frames, 1, 1))
    anchors = points + poses[:, None, 1:4]
    residual = np.full((frames, points_per_frame), 0.012, dtype=float)
    residual[:, 0] = 0.08
    residual[:, 1] = -0.06
    residual += np.arange(frames, dtype=float)[:, None] * 1.0e-4
    variance = np.full_like(residual, 0.0004)
    contamination = np.zeros_like(residual, dtype=bool)
    contamination[:, :2] = True
    axis = np.tile(np.array([1.0, 0.0, 0.0]), (frames, 1))
    observations = {
        "timestamps": timestamps,
        "points_lidar": points,
        "normals_world": normals_all,
        "plane_points_world": anchors,
        "r_list": residual,
        "R_diag_list": variance,
        "contamination_mask": contamination,
        "pose_gt": poses,
        "axis_per_frame": axis,
    }
    motion = {
        "initial_pose": poses[0].copy(),
        "delta_translation_body": np.tile(np.array([0.04, 0.0, 0.0]), (frames - 1, 1)),
        "delta_rotation_vector": np.zeros((frames - 1, 3), dtype=float),
        "translation_covariance_body": np.diag([1.44e-4, 9.0e-6, 9.0e-6]),
        "rotation_covariance_local": np.diag([1.6e-7, 1.6e-7, 6.4e-7]),
    }
    return observations, motion


def _validate_quick_config(config: Mapping[str, Any]) -> None:
    if config.get("mode") != "day8_quick":
        raise ValueError("Day 8 only supports mode=day8_quick")
    if config.get("schema_version") != ONLINE_SCHEMA_VERSION:
        raise ValueError("Day 8 online schema version mismatch")
    if bool(config.get("use_reserved_test")) or bool(config.get("formal_experiment")):
        raise ValueError("Day 8 quick refuses reserved or formal experiment configuration")
    if list(config.get("methods", [])) != ["huber_full", "huber_projected_gain"]:
        raise ValueError("Day 8 methods are frozen to huber_full and huber_projected_gain")
    if float(config.get("directional_information_epsilon", -1.0)) != DIRECTIONAL_INFORMATION_EPSILON:
        raise ValueError("Day 8 directional information epsilon must be 1.0e-12")
    if not bool(config.get("run_logging_equivalence_check")):
        raise ValueError("Day 8 quick must run logging equivalence checks")


def _historical_hashes(root: Path) -> Mapping[str, str]:
    return {
        name: compute_directory_hash(root / name)
        for name in HISTORICAL_ARTIFACT_PATHS
    }


def _observation_checksum(observations: Mapping[str, np.ndarray]) -> str:
    return _array_mapping_checksum(
        {
            key: observations[key]
            for key in [
                "timestamps",
                "points_lidar",
                "normals_world",
                "plane_points_world",
                "r_list",
                "R_diag_list",
            ]
        }
    )


def _array_mapping_checksum(values: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in sorted(values):
        array = np.ascontiguousarray(np.asarray(values[name]))
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def _trajectory_checksum(outputs: Mapping[str, Mapping[str, Any]]) -> str:
    return _array_mapping_checksum(
        {
            f"{method}/poses": output["poses"]
            for method, output in sorted(outputs.items())
        }
    )


def _maximum_array_difference(left: np.ndarray, right: np.ndarray) -> float:
    first = np.asarray(left, dtype=float)
    second = np.asarray(right, dtype=float)
    if first.shape != second.shape:
        return float("inf")
    if not np.all(np.isfinite(first)) or not np.all(np.isfinite(second)):
        return float("inf")
    return float(np.max(np.abs(first - second))) if first.size else 0.0


def _finite_state_violation_count(outputs: Mapping[str, Mapping[str, Any]]) -> int:
    count = 0
    for output in outputs.values():
        for name in ["prior_poses", "poses", "applied_deltas", "full_deltas", "covariances"]:
            count += int(np.count_nonzero(~np.isfinite(np.asarray(output[name], dtype=float))))
    return count


def _git_branch(root: Path) -> str:
    return subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()
