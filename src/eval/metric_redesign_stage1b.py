"""Metric Redesign Stage 1b: paired geometry/observation experiments.

This module is intentionally independent from the Day 1-32 and Stage 1 output
trees. Process trials are repeated outcomes within one sensor run; statistical
tables contain exactly one independent row per geometry/sensor/level run.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import yaml

from degen_detector.exposure_metrics import summarize_exposure_metrics
from degen_detector.odi_tracker import compute_metrics_for_sequence
from eval.hierarchical_statistics import (
    block_bootstrap_spearman,
    paired_monotonicity,
    within_level_residual_spearman,
)
from minibench.motion_simulator import (
    process_noise_checksum,
    save_motion_measurements,
    simulate_motion_measurements,
)
from minibench.observation_simulator import (
    save_observations,
    simulate_sequence_observations,
    simulate_stage1b_observation_degradation,
)
from minibench.scene_generator import generate_open_control, generate_straight_tunnel, load_scene_config, save_sequence
from minibench.toy_lio import load_toy_lio_config, resolve_process_noise_parameters, run_toy_lio, save_pose_est_tum


PRIMARY_METRIC = "mean_inverse_axis_information"
PRIMARY_TARGET = "mean_final_axis_error_squared"
METRIC_DIRECTIONS = {
    PRIMARY_METRIC: 1,
    "harmonic_axis_information": -1,
    "low_axis_information_ratio": 1,
    "longest_low_information_duration_s": 1,
    "ODI_trans_median": 1,
    "lambda_min_trans_normalized_median": -1,
    "condition_number_trans_median": 1,
    "axis_information_normalized_median": -1,
}
LEVEL_ORDERS = {"geometry": ["L1", "L2", "L3", "L4"], "observation": ["O1", "O2", "O3", "O4"]}


def run_stage1b(
    root: Path,
    mode: str,
    common_config_path: Path,
    geometry_config_path: Path,
    observation_config_path: Path,
    detector_config_path: Path,
    motion_config_path: Path,
    run_id: str | None = None,
    workers: int = 1,
    resume: bool = False,
    overwrite: bool = False,
    analyze_run_dir: Path | None = None,
) -> Dict[str, Any]:
    """Run or re-analyze one isolated Stage 1b experiment."""

    started = time.time()
    root = Path(root).resolve()
    if mode == "analyze-only":
        if analyze_run_dir is None:
            raise ValueError("analyze-only requires --run-dir")
        return analyze_existing_run(root, Path(analyze_run_dir), started)
    if mode not in {"quick", "full"}:
        raise ValueError(f"Unsupported Stage 1b mode: {mode}")
    if workers < 1:
        raise ValueError("workers must be positive")

    config_paths = [
        common_config_path,
        geometry_config_path,
        observation_config_path,
        detector_config_path,
        motion_config_path,
    ]
    common, geometry_config, observation_config, detector, motion_raw = [load_yaml(path) for path in config_paths]
    config_hash = combined_config_hash(config_paths)
    resolved_run_id = run_id or default_run_id(config_hash)
    data_run = root / "data/metric_redesign_stage1b" / mode / resolved_run_id
    result_run = root / "results/metric_redesign_stage1b" / mode / resolved_run_id
    prepare_run_directories(data_run, result_run, resume=resume, overwrite=overwrite)
    for relative_dir in ["tables", "figures", "reports", "manifests", "sensors", "trials", "trajectories", "motion"]:
        (result_run / relative_dir).mkdir(parents=True, exist_ok=True)

    preregistration = build_preregistration(common, config_hash, git_commit(root))
    prereg_path = result_run / "manifests/preregistered_analysis.json"
    write_frozen_json(prereg_path, preregistration, resume=resume)
    write_json(
        result_run / "manifests/resolved_config_bundle.json",
        {
            "common": common,
            "geometry": geometry_config,
            "observation": observation_config,
            "detector": detector,
            "motion": motion_raw,
        },
    )

    specs, process_seeds, sensor_seeds = build_stage1b_specs(common, geometry_config, observation_config, mode)
    motion_config = load_toy_lio_config(motion_raw)
    process_rows: List[Dict[str, Any]] = []
    sensor_base_rows: List[Dict[str, Any]] = []
    for spec in specs:
        sequence_dir = data_run / str(spec["sequence_id"])
        generate_or_validate_sequence(sequence_dir, spec)
        for sensor_seed in sensor_seeds:
            sensor_dir = sequence_dir / f"sensor_{sensor_seed:03d}"
            sensor_record_path = result_run / "sensors" / str(spec["sequence_id"]) / f"sensor_{sensor_seed:03d}.json"
            expected_trial_paths = [trial_json_path(result_run, spec, sensor_seed, seed) for seed in process_seeds]
            complete_sensor = sensor_record_path.exists() and all(path.exists() for path in expected_trial_paths)
            observations: Dict[str, np.ndarray] | None = None
            if complete_sensor and resume:
                sensor_base = read_json(sensor_record_path)
            else:
                observations = generate_or_load_observations(
                    sensor_dir,
                    sequence_dir,
                    spec,
                    detector_config_path,
                    observation_config,
                    sensor_seed,
                    resume,
                )
                metrics = compute_metrics_for_sequence(observations, detector)
                write_structured_csv(metrics, sensor_dir / "metrics.csv")
                sensor_base = build_sensor_base_row(
                    root,
                    sequence_dir,
                    sensor_dir,
                    spec,
                    sensor_seed,
                    observations,
                    metrics,
                    common,
                )
                write_json(sensor_record_path, sensor_base)
            sensor_base_rows.append(dict(sensor_base))

            missing_process_seeds = [
                seed for seed, path in zip(process_seeds, expected_trial_paths) if not (resume and path.exists())
            ]
            if missing_process_seeds:
                if observations is None:
                    observations = load_npz(sensor_dir / "observations.npz")
                trial_rows = run_sensor_process_trials(
                    root,
                    result_run,
                    sequence_dir,
                    spec,
                    sensor_seed,
                    observations,
                    detector,
                    motion_config,
                    motion_raw,
                    missing_process_seeds,
                    workers,
                )
                for row in trial_rows:
                    write_json(trial_json_path(result_run, spec, sensor_seed, int(row["process_seed"])), row)
            process_rows.extend(read_json(path) for path in expected_trial_paths)

    write_csv(result_run / "tables/process_trial_summary.csv", process_rows)
    sensor_rows = merge_sensor_process_summaries(sensor_base_rows, process_rows, common)
    write_csv(result_run / "tables/sensor_run_summary.csv", sensor_rows)
    analysis = analyze_stage1b_tables(result_run, sensor_rows, process_rows, common, mode)
    manifest = build_manifest(
        root,
        mode,
        resolved_run_id,
        data_run,
        result_run,
        config_paths,
        config_hash,
        analysis,
        workers,
        time.time() - started,
    )
    write_json(result_run / "manifests/stage1b_manifest.json", manifest)
    return manifest


def analyze_existing_run(root: Path, run_dir: Path, started: float | None = None) -> Dict[str, Any]:
    result_run = run_dir.resolve()
    if not (result_run / "tables/process_trial_summary.csv").exists():
        raise FileNotFoundError("analyze-only requires an existing Stage 1b result run directory")
    bundle = read_json(result_run / "manifests/resolved_config_bundle.json")
    existing_manifest = read_json(result_run / "manifests/stage1b_manifest.json")
    process_rows = read_csv(result_run / "tables/process_trial_summary.csv")
    sensor_rows = read_csv(result_run / "tables/sensor_run_summary.csv")
    common = bundle["common"]
    analysis = analyze_stage1b_tables(result_run, sensor_rows, process_rows, common, str(existing_manifest["mode"]))
    existing_manifest.update(
        {
            "analysis_mode": "analyze-only",
            "runtime_seconds_last_analysis": round(time.time() - (started or time.time()), 6),
            "stage1b_decision": analysis["stage1b_decision"],
            "gates": analysis["gates"],
        }
    )
    write_json(result_run / "manifests/stage1b_manifest.json", existing_manifest)
    return existing_manifest


def prepare_run_directories(data_run: Path, result_run: Path, resume: bool, overwrite: bool) -> None:
    existing = [path for path in [data_run, result_run] if path.exists()]
    if existing and overwrite:
        for path in existing:
            shutil.rmtree(path)
    elif existing and not resume:
        raise FileExistsError(
            f"Stage 1b run already exists: {', '.join(str(path) for path in existing)}; use --resume or --overwrite"
        )
    data_run.mkdir(parents=True, exist_ok=True)
    result_run.mkdir(parents=True, exist_ok=True)


def build_stage1b_specs(
    common: Mapping[str, Any],
    geometry_config: Mapping[str, Any],
    observation_config: Mapping[str, Any],
    mode: str,
) -> Tuple[List[Dict[str, Any]], List[int], List[int]]:
    train_seeds = [int(value) for value in common["train_geometry_seeds"]]
    test_seeds = [int(value) for value in common["test_geometry_seeds"]]
    geometry_seeds = train_seeds + test_seeds
    sensor_seeds = [int(value) for value in common["sensor_seeds"]]
    process_config = common["process_seeds"]
    process_seeds = list(
        range(int(process_config["start"]), int(process_config["start"]) + int(process_config["count"]))
    )
    if mode == "quick":
        geometry_seeds = train_seeds[:1]
        sensor_seeds = sensor_seeds[:1]
        process_seeds = process_seeds[:3]
    scene = common["scene"]
    specs: List[Dict[str, Any]] = []
    for geometry_seed in geometry_seeds:
        split = "train" if geometry_seed in train_seeds else "test"
        specs.append(
            make_spec(
                scene,
                "geometry",
                "OC",
                geometry_seed,
                split,
                scene_family="OC",
                active_patch_count=0,
            )
        )
        for level, values in geometry_config["levels"].items():
            specs.append(
                make_spec(
                    scene,
                    "geometry",
                    str(level),
                    geometry_seed,
                    split,
                    active_patch_count=int(values["active_axial_patch_count"]),
                )
            )
        for level, values in observation_config["levels"].items():
            specs.append(
                make_spec(
                    scene,
                    "observation",
                    str(level),
                    geometry_seed,
                    split,
                    active_patch_count=int(scene["master_axial_patch_pool_size"]),
                    keep_probability=float(values["axial_observation_keep_probability"]),
                )
            )
    return specs, process_seeds, sensor_seeds


def make_spec(
    scene: Mapping[str, Any],
    sweep_type: str,
    level: str,
    geometry_seed: int,
    split: str,
    scene_family: str = "ST",
    active_patch_count: int = 0,
    keep_probability: float | None = None,
) -> Dict[str, Any]:
    sequence_id = f"stage1b_{sweep_type}_{level}_G{geometry_seed}"
    spec: Dict[str, Any] = {
        "sequence_id": sequence_id,
        "sweep_type": sweep_type,
        "level": level,
        "split": split,
        "scene_family": scene_family,
        "difficulty": level,
        "seed_id": f"G{geometry_seed}",
        "motion_id": "M1",
        "random_seed": geometry_seed,
        "geometry_seed": geometry_seed,
        "axis": [1.0, 0.0, 0.0],
        "frames": int(scene["frames"]),
        "dt_s": float(scene["dt_s"]),
        "active_axial_patch_count": active_patch_count,
        "stage1b_master_pool_size": int(scene["master_axial_patch_pool_size"]),
        "expected_degeneracy": f"stage1b_{sweep_type}_{level}",
        "scientific_role": "stage1b_open_control" if scene_family == "OC" else f"stage1b_{sweep_type}_sweep",
    }
    if scene_family == "OC":
        spec.update(
            {
                "length_m": float(scene["open_length_m"]),
                "scene": {"bounds_m": scene["open_bounds_m"], "box_count": int(scene["open_box_count"])},
            }
        )
        spec.pop("stage1b_master_pool_size")
    else:
        spec.update(
            {
                "tunnel_length_m": float(scene["tunnel_length_m"]),
                "width_m": float(scene["width_m"]),
                "height_m": float(scene["height_m"]),
                "scene": {"finite_plane_patches": True},
            }
        )
    if keep_probability is not None:
        spec["axial_observation_keep_probability"] = keep_probability
    return spec


def generate_or_validate_sequence(sequence_dir: Path, spec: Mapping[str, Any]) -> None:
    required = ["gt.tum", "axis.csv", "planes.csv", "scene_metadata.json", "resolved_scene_config.yaml"]
    if all((sequence_dir / name).exists() for name in required):
        return
    sequence_dir.mkdir(parents=True, exist_ok=True)
    config_path = sequence_dir / "resolved_scene_config.yaml"
    config_path.write_text(yaml.safe_dump(dict(spec), sort_keys=False), encoding="utf-8")
    resolved = load_scene_config(config_path)
    sequence = generate_open_control(resolved) if spec["scene_family"] == "OC" else generate_straight_tunnel(resolved)
    save_sequence(sequence, sequence_dir)
    metadata_path = sequence_dir / "scene_metadata.json"
    metadata = read_json(metadata_path)
    metadata.update(
        {
            "sweep_type": spec["sweep_type"],
            "level": spec["level"],
            "split": spec["split"],
            "gt_checksum": sha256_file(sequence_dir / "gt.tum"),
            "planes_checksum": sha256_file(sequence_dir / "planes.csv"),
            "axis_checksum": sha256_file(sequence_dir / "axis.csv"),
        }
    )
    geometry_payload = {
        key: metadata.get(key)
        for key in [
            "geometry_seed",
            "master_pool_checksum",
            "active_patch_ids",
            "geometry_axial_support_score",
            "non_axial_shell_checksum",
            "sampling_weight_checksum",
            "gt_checksum",
            "planes_checksum",
            "axis_checksum",
        ]
    }
    metadata["geometry_metadata_checksum"] = sha256_json(geometry_payload)
    write_json(metadata_path, metadata)


def generate_or_load_observations(
    sensor_dir: Path,
    sequence_dir: Path,
    spec: Mapping[str, Any],
    detector_config_path: Path,
    observation_config: Mapping[str, Any],
    sensor_seed: int,
    resume: bool,
) -> Dict[str, np.ndarray]:
    observation_path = sensor_dir / "observations.npz"
    if resume and observation_path.exists():
        return load_npz(observation_path)
    sensor_dir.mkdir(parents=True, exist_ok=True)
    if spec["sweep_type"] == "observation":
        observations = simulate_stage1b_observation_degradation(
            sequence_dir,
            detector_config_path,
            sensor_seed,
            float(spec["axial_observation_keep_probability"]),
            int(observation_config.get("candidate_multiplier", 8)),
        )
    else:
        observations = simulate_sequence_observations(sequence_dir, detector_config_path, sensor_seed=sensor_seed)
    save_observations(observations, observation_path)
    return observations


def build_sensor_base_row(
    root: Path,
    sequence_dir: Path,
    sensor_dir: Path,
    spec: Mapping[str, Any],
    sensor_seed: int,
    observations: Mapping[str, np.ndarray],
    metrics: np.ndarray,
    common: Mapping[str, Any],
) -> Dict[str, Any]:
    metadata = read_json(sequence_dir / "scene_metadata.json")
    axial_mask = np.asarray(observations.get("is_axial_support", np.zeros_like(observations["r_list"], dtype=bool)))
    total_points = int(axial_mask.size)
    realized_axial = int(np.sum(axial_mask))
    exposure = summarize_exposure_metrics(
        metrics,
        float(common["statistics"]["low_axis_information_threshold"]),
        float(common["statistics"]["exposure_epsilon"]),
        float(common["statistics"]["weak_axis_alignment_threshold"]),
    )
    row: Dict[str, Any] = {
        "sweep_type": spec["sweep_type"],
        "sequence_id": spec["sequence_id"],
        "level": spec["level"],
        "split": spec["split"],
        "scene_family": spec["scene_family"],
        "geometry_seed": int(spec["geometry_seed"]),
        "sensor_seed": int(sensor_seed),
        "geometry_axial_support_score": float(metadata.get("geometry_axial_support_score", 0.0)),
        "active_axial_patch_count": int(metadata.get("active_axial_patch_count", 0)),
        "master_pool_checksum": metadata.get("master_pool_checksum", "open_control"),
        "non_axial_shell_checksum": metadata.get("non_axial_shell_checksum", "open_control"),
        "sampling_weight_checksum": metadata.get("sampling_weight_checksum", "open_control"),
        "gt_checksum": metadata["gt_checksum"],
        "planes_checksum": metadata["planes_checksum"],
        "axis_checksum": metadata["axis_checksum"],
        "geometry_metadata_checksum": metadata["geometry_metadata_checksum"],
        "axial_observation_keep_probability": float(spec.get("axial_observation_keep_probability", 1.0)),
        "requested_points_per_frame": int(observations["packed_J"].shape[1]),
        "realized_total_points": total_points,
        "realized_axial_points": realized_axial,
        "realized_non_axial_points": total_points - realized_axial,
        "realized_axial_point_fraction": realized_axial / max(total_points, 1),
        "axial_candidate_count": int(np.sum(observations.get("axial_candidate_count", axial_mask))),
        "axial_retained_count": int(np.sum(observations.get("axial_retained_count", axial_mask))),
        "observation_checksum": sha256_file(sensor_dir / "observations.npz"),
        "metrics_path": relative(root, sensor_dir / "metrics.csv"),
    }
    for field in [
        "ODI_trans",
        "lambda_min_trans_normalized",
        "condition_number_trans",
        "axis_information_raw",
        "axis_information_normalized",
        "axis_information_ratio",
        "weak_trans_subspace_alignment",
    ]:
        values = np.asarray(metrics[field], dtype=float)
        values = values[np.isfinite(values)]
        row[f"{field}_median"] = float(np.median(values)) if values.size else float("nan")
    row.update(exposure)
    write_json(
        sensor_dir / "observation_metadata.json",
        {
            key: row[key]
            for key in [
                "sequence_id",
                "level",
                "geometry_seed",
                "sensor_seed",
                "requested_points_per_frame",
                "realized_total_points",
                "realized_axial_points",
                "realized_non_axial_points",
                "realized_axial_point_fraction",
                "axial_candidate_count",
                "axial_retained_count",
                "observation_checksum",
            ]
        },
    )
    return row


def run_sensor_process_trials(
    root: Path,
    result_run: Path,
    sequence_dir: Path,
    spec: Mapping[str, Any],
    sensor_seed: int,
    observations: Mapping[str, np.ndarray],
    detector: Mapping[str, Any],
    motion_config: Mapping[str, Any],
    motion_raw: Mapping[str, Any],
    process_seeds: Sequence[int],
    workers: int,
) -> List[Dict[str, Any]]:
    family = str(spec["scene_family"])
    parameters = resolve_process_noise_parameters(family, motion_config)
    profile = str(motion_raw.get("motion_profile_id", "stage1b_straight_m1"))
    if family == "OC":
        profile = f"{profile}_open_control"
    motions: Dict[int, Dict[str, np.ndarray]] = {}
    for process_seed in process_seeds:
        motion = simulate_motion_measurements(
            observations["pose_gt"],
            int(process_seed),
            parameters,
            axes=observations["axis_per_frame"],
            motion_profile_id=profile,
        )
        motions[int(process_seed)] = motion
        motion_path = result_run / "motion" / profile / f"G{int(spec['geometry_seed'])}" / f"process_{process_seed}.npz"
        if not motion_path.exists():
            save_motion_measurements(motion, motion_path)

    def execute(process_seed: int) -> Dict[str, Any]:
        motion = motions[int(process_seed)]
        result = run_toy_lio(
            sequence_dir,
            dict(detector),
            dict(motion_config),
            motion_measurements=motion,
            process_seed=int(process_seed),
            observations_path=observations,
        )
        trajectory_path = (
            result_run
            / "trajectories"
            / str(spec["sequence_id"])
            / f"sensor_{sensor_seed:03d}"
            / f"process_{process_seed}.tum"
        )
        save_pose_est_tum(result["poses"], trajectory_path)
        summary = dict(result["summary"])
        row: Dict[str, Any] = {
            "sweep_type": spec["sweep_type"],
            "sequence_id": spec["sequence_id"],
            "level": spec["level"],
            "split": spec["split"],
            "scene_family": family,
            "geometry_seed": int(spec["geometry_seed"]),
            "sensor_seed": int(sensor_seed),
            "process_seed": int(process_seed),
            "motion_profile_id": profile,
            "process_noise_checksum": process_noise_checksum(motion),
            "trajectory_path": relative(root, trajectory_path),
        }
        row.update({key: float(value) for key, value in summary.items()})
        return row

    if workers == 1 or len(process_seeds) == 1:
        return [execute(seed) for seed in process_seeds]
    with ThreadPoolExecutor(max_workers=min(int(workers), len(process_seeds))) as executor:
        return list(executor.map(execute, process_seeds))


def aggregate_process_targets(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Aggregate repeated process outcomes into one independent sensor row."""

    signed = np.asarray([float(row["final_axis_error_signed"]) for row in rows], dtype=float)
    absolute = np.asarray([float(row["final_axis_error_abs"]) for row in rows], dtype=float)
    squared = np.asarray([float(row["final_axis_error_squared"]) for row in rows], dtype=float)
    axis_rmse = np.asarray([float(row["axis_rmse"]) for row in rows], dtype=float)
    axis_mae = np.asarray([float(row["axis_mae"]) for row in rows], dtype=float)
    if signed.size == 0:
        raise ValueError("At least one process trial is required")
    return {
        "process_trial_count": int(signed.size),
        "mean_final_axis_error_signed": float(np.mean(signed)),
        "variance_final_axis_error": float(np.var(signed, ddof=1)) if signed.size > 1 else 0.0,
        "mean_final_axis_error_squared": float(np.mean(squared)),
        "rmse_final_axis_error": float(np.sqrt(np.mean(squared))),
        "median_final_axis_error_abs": float(np.median(absolute)),
        "q90_final_axis_error_abs": float(np.percentile(absolute, 90.0)),
        "q95_final_axis_error_abs": float(np.percentile(absolute, 95.0)),
        "mean_axis_rmse": float(np.mean(axis_rmse)),
        "variance_axis_rmse": float(np.var(axis_rmse, ddof=1)) if axis_rmse.size > 1 else 0.0,
        "mean_axis_mae": float(np.mean(axis_mae)),
        "failure_probability_005m": float(np.mean(absolute >= 0.05)),
        "failure_probability_010m": float(np.mean(absolute >= 0.10)),
        "failure_probability_020m": float(np.mean(absolute >= 0.20)),
    }


def merge_sensor_process_summaries(
    sensor_base_rows: Sequence[Mapping[str, Any]],
    process_rows: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, int], List[Mapping[str, Any]]] = defaultdict(list)
    for row in process_rows:
        grouped[(str(row["sequence_id"]), int(row["sensor_seed"]))].append(row)
    output = []
    for base in sensor_base_rows:
        key = (str(base["sequence_id"]), int(base["sensor_seed"]))
        row = dict(base)
        row.update(aggregate_process_targets(grouped[key]))
        output.append(row)
    return output


def analyze_stage1b_tables(
    result_run: Path,
    sensor_rows: Sequence[Mapping[str, Any]],
    process_rows: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any],
    mode: str,
) -> Dict[str, Any]:
    tables = result_run / "tables"
    normalized_sensor_rows = [normalize_numeric_row(row) for row in sensor_rows]
    level_rows = build_level_summary(normalized_sensor_rows)
    write_csv(tables / "level_summary.csv", level_rows)

    correlation_tables: Dict[str, List[Dict[str, Any]]] = {}
    for sweep in ["geometry", "observation"]:
        rows = build_correlation_rows(normalized_sensor_rows, sweep, common)
        correlation_tables[sweep] = rows
        write_csv(tables / f"{sweep}_sweep_correlations.csv", rows)
    within_rows = build_within_level_rows(normalized_sensor_rows)
    write_csv(tables / "within_level_correlations.csv", within_rows)
    paired_rows = build_paired_rows(normalized_sensor_rows, common)
    write_csv(tables / "paired_monotonicity.csv", paired_rows)
    comparison_rows = build_train_test_comparison(correlation_tables, within_rows, paired_rows)
    write_csv(tables / "train_test_comparison.csv", comparison_rows)

    evidence_path = result_run.parents[3] / "reports/stage1b_pytest_status.json"
    pytest_evidence = read_json(evidence_path) if evidence_path.exists() else None
    gates = evaluate_stage1b_gates(
        normalized_sensor_rows,
        process_rows,
        correlation_tables,
        within_rows,
        paired_rows,
        common,
        mode,
        pytest_evidence,
    )
    gate_rows = [{"gate": key, "status": value} for key, value in gates.items() if key != "checks"]
    gate_rows.extend(
        {"gate": f"check:{key}", "status": json.dumps(value, sort_keys=True)}
        for key, value in gates["checks"].items()
    )
    write_csv(tables / "gate_summary.csv", gate_rows)
    generate_stage1b_figures(result_run / "figures", normalized_sensor_rows)
    report = build_gate_report(gates, level_rows, correlation_tables, within_rows, paired_rows, normalized_sensor_rows)
    (result_run / "reports/stage1b_gate_report.md").write_text(report, encoding="utf-8")
    return {
        "sequence_count": len({str(row["sequence_id"]) for row in normalized_sensor_rows}),
        "sensor_run_count": len(normalized_sensor_rows),
        "geometry_sensor_run_count": sum(str(row["sweep_type"]) == "geometry" for row in normalized_sensor_rows),
        "geometry_sweep_noncontrol_count": sum(
            str(row["sweep_type"]) == "geometry" and str(row["level"]) != "OC" for row in normalized_sensor_rows
        ),
        "open_control_sensor_run_count": sum(str(row["level"]) == "OC" for row in normalized_sensor_rows),
        "observation_sensor_run_count": sum(str(row["sweep_type"]) == "observation" for row in normalized_sensor_rows),
        "process_trial_count": len(process_rows),
        "gates": gates,
        "stage1b_decision": gates["stage1b"],
    }


def build_level_summary(sensor_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for row in sensor_rows:
        grouped[(str(row["sweep_type"]), str(row["level"]), str(row["split"]))].append(row)
    output = []
    for (sweep, level, split), rows in sorted(grouped.items()):
        output.append(
            {
                "sweep_type": sweep,
                "level": level,
                "split": split,
                "independent_sensor_runs": len(rows),
                "geometry_axial_support_score": median_field(rows, "geometry_axial_support_score"),
                "realized_axial_point_fraction": median_field(rows, "realized_axial_point_fraction"),
                "axis_information_normalized_median": median_field(rows, "axis_information_normalized_median"),
                "mean_inverse_axis_information": median_field(rows, "mean_inverse_axis_information"),
                "ODI_trans_median": median_field(rows, "ODI_trans_median"),
                "mean_final_axis_error_squared": median_field(rows, PRIMARY_TARGET),
            }
        )
    return output


def build_correlation_rows(
    sensor_rows: Sequence[Mapping[str, Any]],
    sweep: str,
    common: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    stats = common["statistics"]
    allowed_levels = set(LEVEL_ORDERS[sweep])
    output = []
    for split in ["train", "test"]:
        rows = [
            row
            for row in sensor_rows
            if str(row["sweep_type"]) == sweep and str(row["level"]) in allowed_levels and str(row["split"]) == split
        ]
        if not rows:
            continue
        for metric, direction in METRIC_DIRECTIONS.items():
            result = block_bootstrap_spearman(
                rows,
                metric,
                PRIMARY_TARGET,
                int(stats["bootstrap_repetitions"]),
                int(stats["bootstrap_seed"]),
            )
            output.append(
                {
                    "sweep_type": sweep,
                    "split": split,
                    "metric_name": metric,
                    "target": PRIMARY_TARGET,
                    "expected_direction": "positive" if direction > 0 else "negative",
                    "rho": result["rho"],
                    "bootstrap_ci_low": result["bootstrap_ci_low"],
                    "bootstrap_ci_high": result["bootstrap_ci_high"],
                    "bootstrap_method": result["bootstrap_method"],
                    "bootstrap_blocks": result["bootstrap_blocks"],
                    "bootstrap_repetitions": result["bootstrap_repetitions"],
                    "independent_sensor_runs": len(rows),
                }
            )
    return output


def build_within_level_rows(sensor_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    output = []
    for sweep, levels in LEVEL_ORDERS.items():
        all_rows = [
            row for row in sensor_rows if str(row["sweep_type"]) == sweep and str(row["level"]) in set(levels)
        ]
        train_rows = [row for row in all_rows if str(row["split"]) == "train"]
        for split in ["train", "test"]:
            rows = [row for row in all_rows if str(row["split"]) == split]
            if not rows:
                continue
            for metric, direction in METRIC_DIRECTIONS.items():
                output.append(
                    {
                        "sweep_type": sweep,
                        "split": split,
                        "metric_name": metric,
                        "target": PRIMARY_TARGET,
                        "expected_direction": "positive" if direction > 0 else "negative",
                        "within_level_residual_spearman": within_level_residual_spearman(
                            rows, train_rows, metric, PRIMARY_TARGET
                        ),
                        "train_level_medians_frozen": True,
                        "independent_sensor_runs": len(rows),
                    }
                )
    return output


def build_paired_rows(
    sensor_rows: Sequence[Mapping[str, Any]], common: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    output = []
    tolerance = float(common["statistics"]["monotonic_tolerance"])
    for sweep, levels in LEVEL_ORDERS.items():
        for split in ["train", "test"]:
            rows = [
                row
                for row in sensor_rows
                if str(row["sweep_type"]) == sweep and str(row["level"]) in set(levels) and str(row["split"]) == split
            ]
            if not rows:
                continue
            for field, direction, kind in [
                (PRIMARY_METRIC, 1, "metric"),
                ("axis_information_normalized_median", -1, "mechanism_metric"),
                ("ODI_trans_median", 1, "baseline_metric"),
                (PRIMARY_TARGET, 1, "target"),
            ]:
                stats = paired_monotonicity(rows, field, levels, direction, tolerance)
                output.append(
                    {
                        "sweep_type": sweep,
                        "split": split,
                        "field": field,
                        "kind": kind,
                        "risk_direction": direction,
                        "metric_monotonic_pair_rate": stats["monotonic_pair_rate"] if kind != "target" else float("nan"),
                        "target_monotonic_pair_rate": stats["monotonic_pair_rate"] if kind == "target" else float("nan"),
                        "median_group_kendall_tau": stats["median_group_kendall_tau"],
                        "positive_tau_group_ratio": stats["positive_tau_group_ratio"],
                        "paired_group_count": stats["paired_group_count"],
                    }
                )
    return output


def build_train_test_comparison(
    correlations: Mapping[str, Sequence[Mapping[str, Any]]],
    within_rows: Sequence[Mapping[str, Any]],
    paired_rows: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    output = []
    for sweep in ["geometry", "observation"]:
        for metric in [PRIMARY_METRIC, "ODI_trans_median"]:
            train = find_row(correlations[sweep], split="train", metric_name=metric)
            test = find_row(correlations[sweep], split="test", metric_name=metric)
            output.append(
                {
                    "sweep_type": sweep,
                    "metric_name": metric,
                    "train_rho": train.get("rho", float("nan")),
                    "train_ci_low": train.get("bootstrap_ci_low", float("nan")),
                    "train_ci_high": train.get("bootstrap_ci_high", float("nan")),
                    "test_rho": test.get("rho", float("nan")),
                    "test_ci_low": test.get("bootstrap_ci_low", float("nan")),
                    "test_ci_high": test.get("bootstrap_ci_high", float("nan")),
                    "test_evaluated_once": True,
                }
            )
    return output


def evaluate_stage1b_gates(
    sensor_rows: Sequence[Mapping[str, Any]],
    process_rows: Sequence[Mapping[str, Any]],
    correlations: Mapping[str, Sequence[Mapping[str, Any]]],
    within_rows: Sequence[Mapping[str, Any]],
    paired_rows: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any],
    mode: str,
    pytest_evidence: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    expected = {"quick": (9, 27), "full": (90, 2700)}[mode]
    sensor_count_ok = len(sensor_rows) == expected[0]
    trial_count_ok = len(process_rows) == expected[1]
    expected_trials_per_sensor = 3 if mode == "quick" else 30
    one_row_per_sensor = len(
        {(str(row["sweep_type"]), str(row["sequence_id"]), str(row["level"]), int(row["geometry_seed"]), int(row["sensor_seed"])) for row in sensor_rows}
    ) == len(sensor_rows)
    aggregation_ok = all(int(row["process_trial_count"]) == expected_trials_per_sensor for row in sensor_rows)
    process_pair_ok = common_process_noise_pairing_pass(process_rows)
    pytest_ok = mode == "quick" or bool(
        pytest_evidence
        and pytest_evidence.get("command") == "pytest -q"
        and pytest_evidence.get("status") == "passed"
        and int(pytest_evidence.get("test_count", 0)) >= 150
    )
    engineering_pass = (
        sensor_count_ok and trial_count_ok and one_row_per_sensor and aggregation_ok and process_pair_ok and pytest_ok
    )

    geometry_rows = [row for row in sensor_rows if str(row["sweep_type"]) == "geometry" and str(row["level"]) != "OC"]
    observation_rows = [row for row in sensor_rows if str(row["sweep_type"]) == "observation"]
    geometry_structure_ok = geometry_structure_mechanism_pass(geometry_rows)
    observation_structure_ok = observation_structure_mechanism_pass(observation_rows)
    required_pair_rate = float(common["statistics"]["mechanism_pair_rate_threshold"])
    required_splits = ["train"] if mode == "quick" else ["train", "test"]
    geometry_axis_rates = [
        float(
            find_row(
                paired_rows, sweep_type="geometry", split=split, field="axis_information_normalized_median"
            ).get("metric_monotonic_pair_rate", float("nan"))
        )
        for split in required_splits
    ]
    observation_axis_rates = [
        float(
            find_row(
                paired_rows, sweep_type="observation", split=split, field="axis_information_normalized_median"
            ).get("metric_monotonic_pair_rate", float("nan"))
        )
        for split in required_splits
    ]
    geometry_axis_ok = all(rate >= required_pair_rate for rate in geometry_axis_rates)
    observation_axis_ok = all(rate >= required_pair_rate for rate in observation_axis_rates)
    mechanism_pass = geometry_structure_ok and observation_structure_ok and geometry_axis_ok and observation_axis_ok

    prediction_pass = mode == "full"
    threshold = float(common["statistics"]["primary_abs_rho_threshold"])
    for sweep in ["geometry", "observation"]:
        primary = find_row(correlations[sweep], split="test", metric_name=PRIMARY_METRIC)
        odi = find_row(correlations[sweep], split="test", metric_name="ODI_trans_median")
        residual = find_row(within_rows, sweep_type=sweep, split="test", metric_name=PRIMARY_METRIC)
        primary_pair = find_row(paired_rows, sweep_type=sweep, split="test", field=PRIMARY_METRIC)
        odi_pair = find_row(paired_rows, sweep_type=sweep, split="test", field="ODI_trans_median")
        rho = float(primary.get("rho", float("nan")))
        ci_low = float(primary.get("bootstrap_ci_low", float("nan")))
        ci_high = float(primary.get("bootstrap_ci_high", float("nan")))
        odi_rho = float(odi.get("rho", float("nan")))
        primary_pair_rate = float(primary_pair.get("metric_monotonic_pair_rate", float("nan")))
        odi_pair_rate = float(odi_pair.get("metric_monotonic_pair_rate", float("nan")))
        residual_rho = float(residual.get("within_level_residual_spearman", float("nan")))
        ci_direction_ok = np.isfinite(ci_low) and np.isfinite(ci_high) and (ci_low + ci_high) > 0.0
        primary_not_worse = (
            np.isfinite(odi_rho)
            and abs(rho) >= abs(odi_rho) - 1.0e-12
            and primary_pair_rate >= odi_pair_rate - 1.0e-12
        )
        prediction_pass = bool(
            prediction_pass
            and np.isfinite(rho)
            and rho > 0.0
            and abs(rho) >= threshold
            and ci_direction_ok
            and np.isfinite(residual_rho)
            and residual_rho > 0.0
            and primary_not_worse
        )
    checks: Dict[str, Any] = {
        "sensor_count": {"actual": len(sensor_rows), "expected": expected[0], "pass": sensor_count_ok},
        "process_trial_count": {"actual": len(process_rows), "expected": expected[1], "pass": trial_count_ok},
        "one_row_per_sensor_run": one_row_per_sensor,
        "process_trials_aggregated": aggregation_ok,
        "common_process_noise": process_pair_ok,
        "full_pytest": dict(pytest_evidence) if pytest_evidence else {"status": "not_required" if mode == "quick" else "missing"},
        "geometry_structure": geometry_structure_ok,
        "observation_geometry_and_retention": observation_structure_ok,
        "geometry_axis_information_pair_rates": geometry_axis_rates,
        "observation_axis_information_pair_rates": observation_axis_rates,
        "prediction_details": {},
    }
    for sweep in ["geometry", "observation"]:
        primary = find_row(correlations[sweep], split="test", metric_name=PRIMARY_METRIC)
        odi = find_row(correlations[sweep], split="test", metric_name="ODI_trans_median")
        residual = find_row(within_rows, sweep_type=sweep, split="test", metric_name=PRIMARY_METRIC)
        primary_pair = find_row(paired_rows, sweep_type=sweep, split="test", field=PRIMARY_METRIC)
        checks["prediction_details"][sweep] = {
            "primary_rho": primary.get("rho", float("nan")),
            "primary_ci": [primary.get("bootstrap_ci_low", float("nan")), primary.get("bootstrap_ci_high", float("nan"))],
            "odi_rho": odi.get("rho", float("nan")),
            "within_level_residual_rho": residual.get("within_level_residual_spearman", float("nan")),
            "primary_monotonic_pair_rate": primary_pair.get("metric_monotonic_pair_rate", float("nan")),
        }
    gates: Dict[str, Any] = {
        "engineering": "ENGINEERING_PASS" if engineering_pass else "ENGINEERING_FAIL",
        "mechanism": "MECHANISM_PASS" if mechanism_pass else "MECHANISM_FAIL",
        "prediction": "PREDICTION_PASS" if prediction_pass else "PREDICTION_FAIL",
        "checks": checks,
    }
    gates["stage1b"] = (
        "STAGE1B_PASS"
        if gates["engineering"].endswith("PASS")
        and gates["mechanism"].endswith("PASS")
        and gates["prediction"].endswith("PASS")
        else "STAGE1B_NO_GO"
    )
    return gates


def common_process_noise_pairing_pass(process_rows: Sequence[Mapping[str, Any]]) -> bool:
    grouped: Dict[Tuple[int, int, str, str], set[str]] = defaultdict(set)
    for row in process_rows:
        if str(row["scene_family"]) == "OC":
            continue
        key = (
            int(row["geometry_seed"]),
            int(row["process_seed"]),
            str(row["motion_profile_id"]),
            str(row["split"]),
        )
        grouped[key].add(str(row["process_noise_checksum"]))
    return bool(grouped) and all(len(values) == 1 for values in grouped.values())


def geometry_structure_mechanism_pass(rows: Sequence[Mapping[str, Any]]) -> bool:
    groups: Dict[Tuple[int, int], Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        groups[(int(row["geometry_seed"]), int(row["sensor_seed"]))][str(row["level"])] = row
    for values in groups.values():
        if not all(level in values for level in LEVEL_ORDERS["geometry"]):
            return False
        support = [float(values[level]["geometry_axial_support_score"]) for level in LEVEL_ORDERS["geometry"]]
        if not (support[0] > support[1] > support[2] > support[3] > 0.0):
            return False
        if len({str(values[level]["non_axial_shell_checksum"]) for level in values}) != 1:
            return False
        if len({str(values[level]["sampling_weight_checksum"]) for level in values}) != 1:
            return False
    return bool(groups)


def observation_structure_mechanism_pass(rows: Sequence[Mapping[str, Any]]) -> bool:
    groups: Dict[Tuple[int, int], Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        groups[(int(row["geometry_seed"]), int(row["sensor_seed"]))][str(row["level"])] = row
    for values in groups.values():
        if not all(level in values for level in LEVEL_ORDERS["observation"]):
            return False
        for checksum in ["gt_checksum", "planes_checksum", "axis_checksum", "geometry_metadata_checksum"]:
            if len({str(values[level][checksum]) for level in values}) != 1:
                return False
        fractions = [float(values[level]["realized_axial_point_fraction"]) for level in LEVEL_ORDERS["observation"]]
        if not all(fractions[index] > fractions[index + 1] for index in range(3)):
            return False
        totals = [int(values[level]["realized_total_points"]) for level in LEVEL_ORDERS["observation"]]
        if len(set(totals)) != 1:
            return False
    return bool(groups)


def generate_stage1b_figures(figures_dir: Path, sensor_rows: Sequence[Mapping[str, Any]]) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    plot_level_field(figures_dir / "geometry_support_by_level.png", sensor_rows, "geometry", "geometry_axial_support_score")
    plot_level_field(
        figures_dir / "realized_axial_fraction_by_level.png",
        sensor_rows,
        "observation",
        "realized_axial_point_fraction",
    )
    plot_two_sweeps(figures_dir / "axis_information_by_level.png", sensor_rows, "axis_information_normalized_median")
    plot_two_sweeps(figures_dir / "target_error_by_level.png", sensor_rows, PRIMARY_TARGET)
    plot_relationship(
        figures_dir / "primary_metric_vs_target_geometry_test.png", sensor_rows, "geometry", PRIMARY_METRIC, PRIMARY_TARGET
    )
    plot_relationship(
        figures_dir / "primary_metric_vs_target_observation_test.png",
        sensor_rows,
        "observation",
        PRIMARY_METRIC,
        PRIMARY_TARGET,
    )
    plot_metric_comparison(figures_dir / "odi_vs_target_comparison.png", sensor_rows)
    plot_paired_trajectories(figures_dir / "paired_level_trajectories.png", sensor_rows)
    plot_within_residuals(figures_dir / "within_level_residual_relationship.png", sensor_rows)
    for path in figures_dir.glob("*.png"):
        if path.stat().st_size < 1000:
            raise RuntimeError(f"Stage 1b figure is unexpectedly small: {path}")
        image = plt.imread(path)
        if image.ndim < 2 or image.shape[0] < 300 or image.shape[1] < 400:
            raise RuntimeError(f"Stage 1b figure has invalid pixel dimensions: {path} {image.shape}")


def plot_level_field(path: Path, rows: Sequence[Mapping[str, Any]], sweep: str, field: str) -> None:
    levels = LEVEL_ORDERS[sweep]
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=120)
    for split, marker in [("train", "o"), ("test", "s")]:
        for index, level in enumerate(levels):
            values = [
                float(row[field])
                for row in rows
                if str(row["sweep_type"]) == sweep and str(row["level"]) == level and str(row["split"]) == split
            ]
            ax.scatter(np.full(len(values), index), values, marker=marker, alpha=0.75, label=split if index == 0 else None)
    ax.set_xticks(range(len(levels)), levels)
    ax.set_xlabel("level")
    ax.set_ylabel(field)
    ax.legend()
    save_figure(fig, path)


def plot_two_sweeps(path: Path, rows: Sequence[Mapping[str, Any]], field: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.0), dpi=120)
    for ax, (sweep, levels) in zip(axes, LEVEL_ORDERS.items()):
        for split, marker in [("train", "o"), ("test", "s")]:
            for index, level in enumerate(levels):
                values = [
                    float(row[field])
                    for row in rows
                    if str(row["sweep_type"]) == sweep
                    and str(row["level"]) == level
                    and str(row["split"]) == split
                ]
                ax.scatter(np.full(len(values), index), values, marker=marker, alpha=0.7, label=split if index == 0 else None)
        ax.set_xticks(range(len(levels)), levels)
        ax.set_title(sweep)
        ax.set_ylabel(field)
        ax.legend()
    save_figure(fig, path)


def plot_relationship(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    sweep: str,
    x_field: str,
    y_field: str,
) -> None:
    selected = [
        row
        for row in rows
        if str(row["sweep_type"]) == sweep
        and str(row["split"]) == "test"
        and str(row["level"]) in set(LEVEL_ORDERS[sweep])
    ]
    fig, ax = plt.subplots(figsize=(6.0, 4.2), dpi=120)
    for level in LEVEL_ORDERS[sweep]:
        subset = [row for row in selected if str(row["level"]) == level]
        ax.scatter([float(row[x_field]) for row in subset], [float(row[y_field]) for row in subset], label=level)
    ax.set_xlabel(x_field)
    ax.set_ylabel(y_field)
    ax.legend()
    save_figure(fig, path)


def plot_metric_comparison(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.0), dpi=120)
    for ax, sweep in zip(axes, ["geometry", "observation"]):
        selected = [
            row
            for row in rows
            if str(row["sweep_type"]) == sweep
            and str(row["split"]) == "test"
            and str(row["level"]) in set(LEVEL_ORDERS[sweep])
        ]
        ax.scatter([float(row["ODI_trans_median"]) for row in selected], [float(row[PRIMARY_TARGET]) for row in selected])
        ax.set_title(sweep)
        ax.set_xlabel("ODI_trans_median")
        ax.set_ylabel(PRIMARY_TARGET)
    save_figure(fig, path)


def plot_paired_trajectories(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.0), dpi=120)
    for ax, (sweep, levels) in zip(axes, LEVEL_ORDERS.items()):
        groups: Dict[Tuple[int, int], Dict[str, float]] = defaultdict(dict)
        for row in rows:
            if str(row["sweep_type"]) == sweep and str(row["level"]) in set(levels):
                groups[(int(row["geometry_seed"]), int(row["sensor_seed"]))][str(row["level"])] = float(
                    row[PRIMARY_METRIC]
                )
        for values in groups.values():
            if all(level in values for level in levels):
                ax.plot(range(len(levels)), [values[level] for level in levels], alpha=0.45)
        ax.set_xticks(range(len(levels)), levels)
        ax.set_title(sweep)
        ax.set_ylabel(PRIMARY_METRIC)
    save_figure(fig, path)


def plot_within_residuals(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.0), dpi=120)
    for ax, (sweep, levels) in zip(axes, LEVEL_ORDERS.items()):
        selected = [row for row in rows if str(row["sweep_type"]) == sweep and str(row["level"]) in set(levels)]
        train = [row for row in selected if str(row["split"]) == "train"]
        medians = {
            level: (
                np.median([float(row[PRIMARY_METRIC]) for row in train if str(row["level"]) == level]),
                np.median([float(row[PRIMARY_TARGET]) for row in train if str(row["level"]) == level]),
            )
            for level in levels
            if any(str(row["level"]) == level for row in train)
        }
        for split, marker in [("train", "o"), ("test", "s")]:
            subset = [row for row in selected if str(row["split"]) == split and str(row["level"]) in medians]
            x = [float(row[PRIMARY_METRIC]) - medians[str(row["level"])][0] for row in subset]
            y = [float(row[PRIMARY_TARGET]) - medians[str(row["level"])][1] for row in subset]
            ax.scatter(x, y, marker=marker, alpha=0.7, label=split)
        ax.axhline(0.0, color="0.7", linewidth=0.8)
        ax.axvline(0.0, color="0.7", linewidth=0.8)
        ax.set_title(sweep)
        ax.set_xlabel("primary metric residual")
        ax.set_ylabel("target residual")
        ax.legend()
    save_figure(fig, path)


def save_figure(fig: Any, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_gate_report(
    gates: Mapping[str, Any],
    level_rows: Sequence[Mapping[str, Any]],
    correlations: Mapping[str, Sequence[Mapping[str, Any]]],
    within_rows: Sequence[Mapping[str, Any]],
    paired_rows: Sequence[Mapping[str, Any]],
    sensor_rows: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# Metric Redesign Stage 1b Gate Report",
        "",
        f"Final decision: **{gates['stage1b']}**.",
        "",
        "Scientific gate failure is reported as a normal completed experiment, not as an engineering exception.",
        "",
        "## Gate summary",
        "",
        f"- {gates['engineering']}",
        f"- {gates['mechanism']}",
        f"- {gates['prediction']}",
        "",
        "### Audited checks",
        "",
    ]
    for name, value in gates["checks"].items():
        lines.append(f"- {name}: `{json.dumps(value, sort_keys=True)}`")
    lines.extend(
        [
        "",
        "## Independent-sample accounting",
        "",
        f"- Independent sensor runs: {len(sensor_rows)}",
        "- One sensor_run_summary row is one independent spectrum sample.",
        "- Process trials are repeated outcomes within a sensor run and are not independent spectrum samples.",
        "",
        "## Level summaries",
        "",
        "| Sweep | Split | Level | N | geometry support | axial fraction | axis information | primary metric | primary target |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in level_rows:
        lines.append(
            f"| {row['sweep_type']} | {row['split']} | {row['level']} | {row['independent_sensor_runs']} | "
            f"{format_float(row['geometry_axial_support_score'])} | {format_float(row['realized_axial_point_fraction'])} | "
            f"{format_float(row['axis_information_normalized_median'])} | "
            f"{format_float(row['mean_inverse_axis_information'])} | "
            f"{format_float(row['mean_final_axis_error_squared'])} |"
        )
    for sweep in ["geometry", "observation"]:
        lines.extend(
            [
                "",
                f"## {sweep.title()} Sweep correlations",
                "",
                "| Split | Metric | Expected | rho | geometry-block bootstrap 95% CI | N |",
                "|---|---|---|---:|---:|---:|",
            ]
        )
        for row in correlations[sweep]:
            lines.append(
                f"| {row['split']} | {row['metric_name']} | {row['expected_direction']} | "
                f"{format_float(row['rho'])} | [{format_float(row['bootstrap_ci_low'])}, "
                f"{format_float(row['bootstrap_ci_high'])}] | {row['independent_sensor_runs']} |"
            )
    lines.extend(["", "## Within-level residual correlations", ""])
    for sweep in ["geometry", "observation"]:
        for split in ["train", "test"]:
            row = find_row(within_rows, sweep_type=sweep, split=split, metric_name=PRIMARY_METRIC)
            if row:
                lines.append(
                    f"- {sweep} {split}: {format_float(row['within_level_residual_spearman'])} "
                    "(train level medians frozen before test)."
                )
    lines.extend(["", "## Paired monotonicity", ""])
    for sweep in ["geometry", "observation"]:
        for split in ["train", "test"]:
            metric = find_row(paired_rows, sweep_type=sweep, split=split, field=PRIMARY_METRIC)
            target = find_row(paired_rows, sweep_type=sweep, split=split, field=PRIMARY_TARGET)
            if metric and target:
                lines.append(
                    f"- {sweep} {split}: metric pair rate={format_float(metric['metric_monotonic_pair_rate'])}; "
                    f"target pair rate={format_float(target['target_monotonic_pair_rate'])}."
                )
    lines.extend(
        [
            "",
            "## Frozen analysis statement",
            "",
            "The primary metric, primary target, epsilon, low-information threshold, transforms, directions, and "
            "bootstrap design were frozen before test evaluation. Test geometry seeds were evaluated once; the "
            "program does not sweep test-set parameters.",
            "",
            "## Claim boundary",
            "",
            "This stage uses finite synthetic plane patches and a 6DoF motion-propagation surrogate. Frame 0 uses "
            "the known initial pose; later estimator propagation and residuals do not read GT. This stage does not "
            "implement a weak-subspace update, does not integrate FAST-LIO2, does not validate ODI as a finished "
            "method, and is not a complete Degen-LIO estimator.",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(
    root: Path,
    mode: str,
    run_id: str,
    data_run: Path,
    result_run: Path,
    config_paths: Sequence[Path],
    config_hash: str,
    analysis: Mapping[str, Any],
    workers: int,
    runtime: float,
) -> Dict[str, Any]:
    expected = {"quick": (9, 27), "full": (90, 2700)}[mode]
    actual = (int(analysis["sensor_run_count"]), int(analysis["process_trial_count"]))
    missing = [] if actual == expected else [f"expected_counts={expected};actual_counts={actual}"]
    return {
        "status": "OK" if not missing else "INCOMPLETE",
        "mode": mode,
        "run_id": run_id,
        "git_commit": git_commit(root),
        "config_hash": config_hash,
        "config_hashes": {relative(root, path): sha256_file(path) for path in config_paths},
        "data_run_dir": relative(root, data_run),
        "result_run_dir": relative(root, result_run),
        "workers": int(workers),
        "sequence_count": int(analysis["sequence_count"]),
        "sensor_run_count": actual[0],
        "geometry_sensor_run_count": int(analysis["geometry_sensor_run_count"]),
        "geometry_sweep_noncontrol_count": int(analysis["geometry_sweep_noncontrol_count"]),
        "open_control_sensor_run_count": int(analysis["open_control_sensor_run_count"]),
        "observation_sensor_run_count": int(analysis["observation_sensor_run_count"]),
        "process_trial_count": actual[1],
        "independent_spectrum_sample_count": actual[0],
        "runtime_seconds": round(float(runtime), 6),
        "gates": analysis["gates"],
        "stage1b_decision": analysis["stage1b_decision"],
        "missing_artifacts": missing,
        "output_paths": [
            relative(root, result_run / "tables/process_trial_summary.csv"),
            relative(root, result_run / "tables/sensor_run_summary.csv"),
            relative(root, result_run / "tables/level_summary.csv"),
            relative(root, result_run / "tables/paired_monotonicity.csv"),
            relative(root, result_run / "tables/geometry_sweep_correlations.csv"),
            relative(root, result_run / "tables/observation_sweep_correlations.csv"),
            relative(root, result_run / "tables/within_level_correlations.csv"),
            relative(root, result_run / "tables/train_test_comparison.csv"),
            relative(root, result_run / "tables/gate_summary.csv"),
            relative(root, result_run / "reports/stage1b_gate_report.md"),
        ],
    }


def build_preregistration(common: Mapping[str, Any], config_hash: str, commit: str) -> Dict[str, Any]:
    prereg = dict(common["preregistered_analysis"])
    prereg.update(
        {
            "thresholds": {
                "low_axis_information": common["statistics"]["low_axis_information_threshold"],
                "weak_axis_alignment": common["statistics"]["weak_axis_alignment_threshold"],
                "primary_abs_rho": common["statistics"]["primary_abs_rho_threshold"],
                "failure_m": common["statistics"]["failure_thresholds_m"],
            },
            "epsilon": common["statistics"]["exposure_epsilon"],
            "normalization": "H_trans divided by effective sample size",
            "log_transform": False,
            "train_seeds": list(common["train_geometry_seeds"]),
            "test_seeds": list(common["test_geometry_seeds"]),
            "config_hash": config_hash,
            "git_commit": commit,
        }
    )
    return prereg


def trial_json_path(result_run: Path, spec: Mapping[str, Any], sensor_seed: int, process_seed: int) -> Path:
    return (
        result_run
        / "trials"
        / str(spec["sequence_id"])
        / f"sensor_{sensor_seed:03d}"
        / f"process_{process_seed}.json"
    )


def default_run_id(config_hash: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{config_hash[:10]}"


def combined_config_hash(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.name).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_yaml(path: Path) -> Dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def load_npz(path: Path) -> Dict[str, np.ndarray]:
    with np.load(path) as loaded:
        return {key: loaded[key].copy() for key in loaded.files}


def read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON mapping in {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=True) + "\n", encoding="utf-8")


def write_frozen_json(path: Path, value: Mapping[str, Any], resume: bool) -> None:
    if path.exists():
        if read_json(path) != dict(value):
            raise ValueError("Resume refused because preregistered_analysis.json would change")
        return
    write_json(path, value)


def read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_structured_csv(rows: np.ndarray, path: Path) -> None:
    names = list(rows.dtype.names or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name].item() for name in names})


def normalize_numeric_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    output = dict(row)
    integer_fields = {
        "geometry_seed",
        "sensor_seed",
        "process_trial_count",
        "active_axial_patch_count",
        "requested_points_per_frame",
        "realized_total_points",
        "realized_axial_points",
        "realized_non_axial_points",
        "axial_candidate_count",
        "axial_retained_count",
    }
    string_fields = {
        "sweep_type",
        "sequence_id",
        "level",
        "split",
        "scene_family",
        "master_pool_checksum",
        "non_axial_shell_checksum",
        "sampling_weight_checksum",
        "gt_checksum",
        "planes_checksum",
        "axis_checksum",
        "geometry_metadata_checksum",
        "observation_checksum",
        "metrics_path",
    }
    for key, value in list(output.items()):
        if key in string_fields:
            continue
        if key in integer_fields:
            output[key] = int(float(value))
            continue
        if isinstance(value, str):
            try:
                output[key] = float(value)
            except ValueError:
                pass
    return output


def median_field(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = np.asarray([float(row[field]) for row in rows], dtype=float)
    values = values[np.isfinite(values)]
    return float(np.median(values)) if values.size else float("nan")


def find_row(rows: Sequence[Mapping[str, Any]], **criteria: Any) -> Dict[str, Any]:
    for row in rows:
        if all(str(row.get(key)) == str(value) for key, value in criteria.items()):
            return dict(row)
    return {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def format_float(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return "nan" if not np.isfinite(number) else f"{number:.6g}"
