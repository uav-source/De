"""Paired Development/Test pipeline for Weak-Subspace Update Stage 2B."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from functools import partial
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from degen_detector.odi_tracker import compute_metrics_for_frame
from eval.analysis_lock import (
    compute_bundle_hash,
    compute_source_tree_hash,
    git_commit,
    git_path_commit,
    git_status_clean,
    sha256_file,
)
from eval.synthetic_pipeline_common import (
    generate_or_load_observations,
    generate_or_validate_sequence,
    load_npz,
    load_yaml,
    make_spec,
    read_csv,
    read_json,
    relative,
    write_csv,
    write_json,
)
from eval.update_metrics import compute_update_metrics
from eval.weak_update_stage2b_lock import (
    STAGE2A_LOCK,
    build_update_lock,
    stage2b_config_paths,
    stage2b_source_paths,
    validate_reserved_test_seeds,
    validate_seed_isolation,
    verify_update_lock,
)
from minibench.correspondence_stress import apply_correspondence_stress
from minibench.map_lio import linearize_point_to_plane, run_map_lio
from minibench.motion_simulator import (
    compose_pose_with_body_increment,
    process_noise_checksum,
    simulate_motion_measurements,
)
from minibench.nested_geometry_observations import array_checksum, simulate_nested_geometry_observations
from minibench.observation_simulator import frame_planes, load_sequence, save_observations


METHODS = ["motion_only", "huber_full", "huber_global", "huber_selective", "huber_oracle_selective"]
LEVELS = {"geometry": ["L1", "L2", "L3", "L4"], "observation": ["O1", "O2", "O3", "O4"]}
SEVERE = {"L3", "L4", "O3", "O4"}
METRICS = ["axis_rmse", "strong_translation_rmse", "orientation_rmse_rad", "trajectory_rmse_3d"]


def run_weak_update_stage2b(
    root: Path,
    phase: str,
    run_id: str,
    workers: int = 1,
    resume: bool = False,
    overwrite: bool = False,
    update_lock_path: Path | None = None,
) -> Dict[str, Any]:
    if phase not in {"quick", "development", "test"}:
        raise ValueError(f"unsupported Stage 2B phase: {phase}")
    if int(workers) < 1:
        raise ValueError("workers must be at least one")
    root = Path(root).resolve()
    common = load_yaml(root / "configs/update/stage2b_common.yaml")
    phase_config = normalize_phase_config(load_yaml(root / f"configs/update/stage2b_{phase}.yaml"))
    development = normalize_phase_config(load_yaml(root / "configs/update/stage2b_development.yaml"))
    reserved_test = normalize_phase_config(load_yaml(root / "configs/update/stage2b_test.yaml"))
    validate_seed_isolation(development, reserved_test)
    stress_config = load_yaml(root / "configs/update/stage2b_stress.yaml")
    motion_config = load_yaml(root / "configs/toy_lio/motion_surrogate_stage2b.yaml")
    detector_config = load_yaml(root / "configs/detector/odi_stage2a.yaml")

    lock = None
    lock_checks = None
    provenance = None
    if phase == "test":
        if update_lock_path is None or not Path(update_lock_path).exists():
            raise RuntimeError("REFUSE_TEST_EXECUTION: committed update lock is required")
        lock = read_json(Path(update_lock_path))
        lock_checks = verify_update_lock(root, lock, require_clean=True)
        validate_reserved_test_seeds(phase_config, lock)
        git_path_commit(root, Path(update_lock_path))
        provenance_path = root / "results/weak_update_stage2b/pytest_provenance.json"
        if not provenance_path.exists():
            raise RuntimeError("REFUSE_TEST_EXECUTION: current-commit pytest provenance is required")
        provenance = read_json(provenance_path)
        if not (
            provenance.get("status") == "passed"
            and int(provenance.get("return_code", -1)) == 0
            and provenance.get("git_commit") == git_commit(root)
            and bool(provenance.get("git_status_clean"))
        ):
            raise RuntimeError("REFUSE_TEST_EXECUTION: pytest provenance does not match current commit")

    data_run = root / "data/weak_update_stage2b" / phase / run_id
    result_run = root / "results/weak_update_stage2b" / phase / run_id
    prepare_run_directories(data_run, result_run, resume, overwrite)
    for name in ["tables", "reports", "figures", "manifests"]:
        (result_run / name).mkdir(parents=True, exist_ok=True)
    started = time.time()
    blocks, stress_audit = prepare_blocks(
        root, data_run, phase, phase_config, common, detector_config, stress_config, resume
    )
    if len(blocks) != int(phase_config["expected_sensor_stress_blocks"]):
        raise RuntimeError("Stage 2B sensor-stress block count is incomplete")

    if phase == "test":
        threshold = {
            "online_odi_threshold": float(lock["online_odi_threshold"]),
            "odi_control_quantile": float(lock["odi_control_quantile"]),
            "calibration_source": "locked_development_motion_prior_open_control",
        }
        selected_alpha = float(lock["selected_attenuation_alpha"])
        alpha_rows = [dict(row) for row in lock["alpha_selection_table"]]
        trial_rows = run_locked_trials(
            root, blocks, phase_config, common, detector_config, motion_config, stress_config,
            threshold["online_odi_threshold"], selected_alpha, workers,
        )
    else:
        threshold = calibrate_online_threshold(
            root, blocks, phase_config, common, detector_config, motion_config, stress_config
        )
        write_json(result_run / "online_odi_threshold.json", threshold)
        base_rows, candidate_rows = run_development_candidates(
            root, blocks, phase_config, common, detector_config, motion_config, stress_config,
            threshold["online_odi_threshold"], workers,
        )
        alpha_rows, selected_alpha = select_attenuation_alpha(base_rows, candidate_rows, common)
        write_csv(result_run / "tables/alpha_selection.csv", alpha_rows)
        if selected_alpha is None:
            manifest = build_manifest(
                root, phase, run_id, data_run, result_run, phase_config, common, threshold,
                None, [], blocks, started, provenance, lock_checks,
            )
            manifest["status"] = "DEVELOPMENT_NO_GO"
            manifest["alpha_selection"] = alpha_rows
            write_json(result_run / f"manifests/{phase}_manifest.json", manifest)
            return manifest
        trial_rows = complete_selected_development_trials(
            root, blocks, phase_config, common, detector_config, motion_config, stress_config,
            threshold["online_odi_threshold"], selected_alpha, base_rows, candidate_rows, workers,
        )

    expected_trials = int(phase_config["expected_method_trials"])
    if len(trial_rows) != expected_trials:
        raise RuntimeError(f"Stage 2B method trial count {len(trial_rows)} != {expected_trials}")
    pairing_audit = audit_method_pairing(trial_rows)
    method_summary = aggregate_method_trials(trial_rows)
    paired = build_paired_differences(trial_rows)
    write_csv(result_run / "tables/method_trial_summary.csv", trial_rows)
    write_csv(result_run / "tables/sensor_stress_method_summary.csv", method_summary)
    write_csv(result_run / "tables/paired_method_differences.csv", paired)
    write_csv(result_run / "tables/alpha_selection.csv", alpha_rows)
    write_csv(result_run / "tables/pairing_audit.csv", pairing_audit)
    write_csv(result_run / "tables/stress_audit.csv", stress_audit)

    analyses = analyze_trial_results(trial_rows, common)
    for name, rows in analyses["tables"].items():
        write_csv(result_run / f"tables/{name}.csv", rows)
    gates = None
    authorizations = None
    if phase == "test":
        gates = evaluate_stage2b_gates(
            trial_rows, analyses, pairing_audit, stress_audit, common, lock_checks or {}, provenance
        )
        authorizations = {
            **stage2b_authorizations(gates),
        }
        write_gate_outputs(result_run, gates, authorizations, analyses)
    else:
        (result_run / "reports/development_report.md").write_text(
            build_development_report(selected_alpha, threshold, alpha_rows, len(blocks), len(trial_rows)),
            encoding="utf-8",
        )
    generate_figures(result_run, trial_rows, alpha_rows)
    manifest = build_manifest(
        root, phase, run_id, data_run, result_run, phase_config, common, threshold,
        selected_alpha, trial_rows, blocks, started, provenance, lock_checks,
    )
    manifest["alpha_selection"] = alpha_rows
    manifest["pairing_violation_count"] = sum(not bool(row["pairing_valid"]) for row in pairing_audit)
    manifest["solver_failure_count"] = sum(int(row["solver_failure"]) for row in trial_rows)
    if gates is not None:
        manifest["gates"] = gates
        manifest["authorizations"] = authorizations
    write_json(result_run / f"manifests/{phase}_manifest.json", manifest)
    if phase == "test":
        export_current_artifacts(root, result_run, Path(update_lock_path), manifest)
    return manifest


def normalize_phase_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    output = dict(config)
    for field in ["geometry_seeds", "sensor_seeds", "process_seeds"]:
        output[field] = [int(value) for value in config[field]]
    return output


def prepare_run_directories(data_run: Path, result_run: Path, resume: bool, overwrite: bool) -> None:
    existing = [path for path in [data_run, result_run] if path.exists()]
    if existing and overwrite:
        for path in existing:
            shutil.rmtree(path)
    elif existing and not resume:
        raise FileExistsError("Stage 2B run exists; use --resume or --overwrite")
    data_run.mkdir(parents=True, exist_ok=True)
    result_run.mkdir(parents=True, exist_ok=True)


def build_stage2b_specs(common: Mapping[str, Any], geometry_seed: int, phase: str) -> List[Dict[str, Any]]:
    scene = common["scene"]
    control = make_spec(scene, "geometry", "OC", geometry_seed, phase, scene_family="OC")
    control["sequence_id"] = f"stage2b_{phase}_open_control_G{geometry_seed}"
    specs = [control]
    for level, count in common["geometry_levels"].items():
        spec = make_spec(scene, "geometry", str(level), geometry_seed, phase, active_patch_count=int(count))
        spec["sequence_id"] = f"stage2b_{phase}_geometry_{level}_G{geometry_seed}"
        specs.append(spec)
    for level, probability in common["observation_levels"].items():
        spec = make_spec(
            scene, "observation", str(level), geometry_seed, phase,
            active_patch_count=int(scene["master_axial_patch_pool_size"]),
            keep_probability=float(probability),
        )
        spec["sequence_id"] = f"stage2b_{phase}_observation_{level}_G{geometry_seed}"
        specs.append(spec)
    return specs


def prepare_blocks(
    root: Path,
    data_run: Path,
    phase: str,
    phase_config: Mapping[str, Any],
    common: Mapping[str, Any],
    detector_config: Mapping[str, Any],
    stress_config: Mapping[str, Any],
    resume: bool,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    blocks: List[Dict[str, Any]] = []
    stress_rows: List[Dict[str, Any]] = []
    detector_path = root / "configs/detector/odi_stage2a.yaml"
    for geometry_seed in phase_config["geometry_seeds"]:
        for spec in build_stage2b_specs(common, geometry_seed, phase):
            sequence_dir = data_run / spec["sequence_id"]
            generate_or_validate_sequence(sequence_dir, spec)
            for sensor_seed in phase_config["sensor_seeds"]:
                sensor_dir = sequence_dir / f"sensor_{sensor_seed:03d}"
                observation_path = sensor_dir / "observations.npz"
                if resume and observation_path.exists():
                    observations = load_npz(observation_path)
                elif spec["sweep_type"] == "geometry" and spec["level"] in LEVELS["geometry"]:
                    sensor_dir.mkdir(parents=True, exist_ok=True)
                    observations = simulate_nested_geometry_observations(
                        sequence_dir, detector_path, geometry_seed, sensor_seed,
                        float(common["geometry_points_per_square_meter"]),
                        int(common["geometry_min_points_per_patch"]),
                    )
                    save_observations(observations, observation_path)
                else:
                    observations = generate_or_load_observations(
                        sensor_dir, sequence_dir, spec, detector_path,
                        {"candidate_multiplier": int(common["observation_candidate_multiplier"])},
                        sensor_seed, resume,
                    )
                patch_ids = observation_patch_ids(sequence_dir, observations)
                for stress_name in common["stress_names"]:
                    stressed = apply_correspondence_stress(
                        observations, stress_name, stress_config, "weak_update_stage2b",
                        geometry_seed, sensor_seed, patch_ids,
                    )
                    audit = stress_mechanism_audit(
                        spec,
                        sensor_seed,
                        stress_name,
                        observations,
                        stressed,
                        patch_ids,
                        stress_config,
                    )
                    stress_rows.append(audit)
                    blocks.append(
                        {
                            "sweep": sweep_name(spec),
                            "level": spec["level"],
                            "stress": stress_name,
                            "geometry_seed": geometry_seed,
                            "sensor_seed": sensor_seed,
                            "sequence_dir": relative(root, sequence_dir),
                            "observation_path": relative(root, observation_path),
                            "observation_checksum": observation_checksum(observations),
                            "stress_checksum": str(stressed["stress_checksum"].item()),
                        }
                    )
    return blocks, stress_rows


def observation_patch_ids(sequence_dir: Path, observations: Mapping[str, np.ndarray]) -> np.ndarray:
    if "measurement_patch_ids" in observations:
        return np.asarray(observations["measurement_patch_ids"]).astype(str)
    sequence = load_sequence(sequence_dir)
    indices = np.asarray(observations["plane_indices"], dtype=int)
    output = np.empty(indices.shape, dtype="U64")
    for frame in range(indices.shape[0]):
        planes = frame_planes(sequence, frame)
        output[frame] = [planes[int(index)].plane_id for index in indices[frame]]
    return output


def load_stressed_block(
    root: Path,
    block: Mapping[str, Any],
    stress_config: Mapping[str, Any],
) -> tuple[Dict[str, np.ndarray], np.ndarray]:
    observations = load_npz(root / str(block["observation_path"]))
    patches = observation_patch_ids(root / str(block["sequence_dir"]), observations)
    stressed = apply_correspondence_stress(
        observations, str(block["stress"]), stress_config, "weak_update_stage2b",
        int(block["geometry_seed"]), int(block["sensor_seed"]), patches,
    )
    return stressed, patches


def make_motion(
    observations: Mapping[str, np.ndarray],
    process_seed: int,
    geometry_seed: int,
    sensor_seed: int,
    motion_config: Mapping[str, Any],
) -> Dict[str, np.ndarray]:
    return simulate_motion_measurements(
        np.asarray(observations["pose_gt"]), process_seed, dict(motion_config),
        axes=None, motion_profile_id=str(motion_config["motion_profile_id"]),
        experiment_family="weak_update_stage2b", geometry_seed=geometry_seed,
        sensor_seed=sensor_seed,
    )


def calibrate_online_threshold(
    root: Path,
    blocks: Sequence[Mapping[str, Any]],
    phase_config: Mapping[str, Any],
    common: Mapping[str, Any],
    detector_config: Mapping[str, Any],
    motion_config: Mapping[str, Any],
    stress_config: Mapping[str, Any],
) -> Dict[str, Any]:
    values = []
    controls = [block for block in blocks if block["level"] == "OC" and block["stress"] == "clean"]
    for block in controls:
        observations, _ = load_stressed_block(root, block, stress_config)
        for process_seed in phase_config["process_seeds"]:
            motion = make_motion(
                observations, process_seed, int(block["geometry_seed"]), int(block["sensor_seed"]), motion_config
            )
            values.extend(motion_prior_odi(observations, motion, detector_config))
    quantile = float(common["odi_control_quantile"])
    array = np.asarray(values, dtype=float)
    return {
        "online_odi_threshold": float(np.quantile(array, quantile)),
        "odi_control_quantile": quantile,
        "calibration_source": "development_motion_prior_open_control_only",
        "calibration_frame_count": int(array.size),
        "calibration_data_sha256": array_checksum(array),
    }


def motion_prior_odi(
    observations: Mapping[str, np.ndarray],
    motion: Mapping[str, np.ndarray],
    detector_config: Mapping[str, Any],
) -> List[float]:
    pose = np.asarray(motion["initial_pose"], dtype=float)
    output = []
    for frame in range(1, len(observations["timestamps"])):
        pose = compose_pose_with_body_increment(
            pose, motion["delta_translation_body"][frame - 1], motion["delta_rotation_vector"][frame - 1]
        )
        J, _ = linearize_point_to_plane(
            pose, observations["points_lidar"][frame], observations["normals_world"][frame],
            observations["plane_points_world"][frame], observations["r_list"][frame],
        )
        metrics = compute_metrics_for_frame(J, observations["R_diag_list"][frame], dict(detector_config), axis=None)
        output.append(float(metrics["ODI_trans"]))
    return output


def run_development_candidates(
    root: Path,
    blocks: Sequence[Mapping[str, Any]],
    phase_config: Mapping[str, Any],
    common: Mapping[str, Any],
    detector_config: Mapping[str, Any],
    motion_config: Mapping[str, Any],
    stress_config: Mapping[str, Any],
    threshold: float,
    workers: int = 1,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    base_rows: List[Dict[str, Any]] = []
    candidate_rows: List[Dict[str, Any]] = []
    function = partial(
        _run_development_block,
        root=root,
        phase_config=phase_config,
        common=common,
        detector_config=detector_config,
        motion_config=motion_config,
        stress_config=stress_config,
        threshold=threshold,
    )
    for local_base, local_candidates in map_paired_blocks(blocks, function, workers):
        base_rows.extend(local_base)
        candidate_rows.extend(local_candidates)
    return base_rows, candidate_rows


def complete_selected_development_trials(
    root: Path,
    blocks: Sequence[Mapping[str, Any]],
    phase_config: Mapping[str, Any],
    common: Mapping[str, Any],
    detector_config: Mapping[str, Any],
    motion_config: Mapping[str, Any],
    stress_config: Mapping[str, Any],
    threshold: float,
    selected_alpha: float,
    base_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    workers: int = 1,
) -> List[Dict[str, Any]]:
    output = [dict(row) for row in base_rows]
    output.extend(
        {key: value for key, value in row.items() if key != "candidate_alpha"}
        for row in candidate_rows if float(row["candidate_alpha"]) == float(selected_alpha)
    )
    function = partial(
        _run_completion_block,
        root=root,
        phase_config=phase_config,
        common=common,
        detector_config=detector_config,
        motion_config=motion_config,
        stress_config=stress_config,
        threshold=threshold,
        selected_alpha=selected_alpha,
    )
    for local in map_paired_blocks(blocks, function, workers):
        output.extend(local)
    return output


def run_locked_trials(
    root: Path,
    blocks: Sequence[Mapping[str, Any]],
    phase_config: Mapping[str, Any],
    common: Mapping[str, Any],
    detector_config: Mapping[str, Any],
    motion_config: Mapping[str, Any],
    stress_config: Mapping[str, Any],
    threshold: float,
    selected_alpha: float,
    workers: int = 1,
) -> List[Dict[str, Any]]:
    output = []
    function = partial(
        _run_locked_block,
        root=root,
        phase_config=phase_config,
        common=common,
        detector_config=detector_config,
        motion_config=motion_config,
        stress_config=stress_config,
        threshold=threshold,
        selected_alpha=selected_alpha,
    )
    for local in map_paired_blocks(blocks, function, workers):
        output.extend(local)
    return output


def map_paired_blocks(blocks: Sequence[Mapping[str, Any]], function, workers: int):
    """Map independent blocks in input order while keeping paired trials local."""

    if int(workers) == 1:
        return map(function, blocks)
    executor = ProcessPoolExecutor(max_workers=int(workers))

    def ordered_results():
        try:
            yield from executor.map(function, blocks)
        finally:
            executor.shutdown(wait=True)

    return ordered_results()


def _run_development_block(
    block: Mapping[str, Any], *, root: Path, phase_config: Mapping[str, Any],
    common: Mapping[str, Any], detector_config: Mapping[str, Any],
    motion_config: Mapping[str, Any], stress_config: Mapping[str, Any], threshold: float,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    local_base: List[Dict[str, Any]] = []
    local_candidates: List[Dict[str, Any]] = []
    observations, _ = load_stressed_block(root, block, stress_config)
    for process_seed in phase_config["process_seeds"]:
        motion = make_motion(
            observations, process_seed, int(block["geometry_seed"]),
            int(block["sensor_seed"]), motion_config,
        )
        for method in ["motion_only", "huber_full"]:
            local_base.append(run_method_trial(
                block, observations, motion, process_seed, method, threshold,
                1.0, detector_config, common,
            ))
        for alpha in common["attenuation_alpha_candidates"]:
            row = run_method_trial(
                block, observations, motion, process_seed, "huber_selective",
                threshold, float(alpha), detector_config, common,
            )
            row["candidate_alpha"] = float(alpha)
            local_candidates.append(row)
    return local_base, local_candidates


def _run_completion_block(
    block: Mapping[str, Any], *, root: Path, phase_config: Mapping[str, Any],
    common: Mapping[str, Any], detector_config: Mapping[str, Any],
    motion_config: Mapping[str, Any], stress_config: Mapping[str, Any], threshold: float,
    selected_alpha: float,
) -> List[Dict[str, Any]]:
    local = []
    observations, _ = load_stressed_block(root, block, stress_config)
    for process_seed in phase_config["process_seeds"]:
        motion = make_motion(
            observations, process_seed, int(block["geometry_seed"]),
            int(block["sensor_seed"]), motion_config,
        )
        for method in ["huber_global", "huber_oracle_selective"]:
            local.append(run_method_trial(
                block, observations, motion, process_seed, method, threshold,
                selected_alpha, detector_config, common,
            ))
    return local


def _run_locked_block(
    block: Mapping[str, Any], *, root: Path, phase_config: Mapping[str, Any],
    common: Mapping[str, Any], detector_config: Mapping[str, Any],
    motion_config: Mapping[str, Any], stress_config: Mapping[str, Any], threshold: float,
    selected_alpha: float,
) -> List[Dict[str, Any]]:
    local = []
    observations, _ = load_stressed_block(root, block, stress_config)
    for process_seed in phase_config["process_seeds"]:
        motion = make_motion(
            observations, process_seed, int(block["geometry_seed"]),
            int(block["sensor_seed"]), motion_config,
        )
        for method in METHODS:
            alpha = selected_alpha if method in {
                "huber_global", "huber_selective", "huber_oracle_selective",
            } else 1.0
            local.append(run_method_trial(
                block, observations, motion, process_seed, method, threshold,
                alpha, detector_config, common,
            ))
    return local


def run_method_trial(
    block: Mapping[str, Any],
    observations: Mapping[str, np.ndarray],
    motion: Mapping[str, np.ndarray],
    process_seed: int,
    method: str,
    threshold: float,
    alpha: float,
    detector_config: Mapping[str, Any],
    common: Mapping[str, Any],
) -> Dict[str, Any]:
    started = time.perf_counter()
    oracle = np.asarray(observations["axis_per_frame"], dtype=float) if method == "huber_oracle_selective" else None
    output = run_map_lio(
        observations, motion, detector_config, common, method, threshold, alpha, oracle_directions=oracle
    )
    metrics = compute_update_metrics(
        output["poses"], observations["pose_gt"], observations["axis_per_frame"],
        output["frame_diagnostics"], output["covariances"],
    )
    row = {
        "sweep": block["sweep"], "level": block["level"], "stress": block["stress"],
        "geometry_seed": int(block["geometry_seed"]), "sensor_seed": int(block["sensor_seed"]),
        "process_seed": int(process_seed), "method": method,
        "attenuation_alpha": float(alpha),
        "observation_checksum": block["observation_checksum"],
        "stress_checksum": block["stress_checksum"],
        "process_noise_checksum": process_noise_checksum(dict(motion)),
        "initial_state_checksum": array_checksum(np.asarray(motion["initial_pose"])),
        "initial_covariance_checksum": array_checksum(
            np.diag(np.asarray(common["initial_covariance_diag"], dtype=float))
        ),
        "solver_failure": int(output["solver_failure_count"] > 0),
        "runtime_s": time.perf_counter() - started,
    }
    row.update(metrics)
    return row


def select_attenuation_alpha(
    base_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any],
) -> tuple[List[Dict[str, Any]], float | None]:
    full = index_rows([row for row in base_rows if row["method"] == "huber_full"])
    table = []
    for alpha in common["attenuation_alpha_candidates"]:
        candidates = [row for row in candidate_rows if float(row["candidate_alpha"]) == float(alpha)]
        pairs = [(row, full[trial_key(row)]) for row in candidates]
        oc = [pair for pair in pairs if pair[0]["level"] == "OC" and pair[0]["stress"] == "clean"]
        clean = [pair for pair in pairs if pair[0]["stress"] == "clean"]
        severe = [pair for pair in pairs if pair[0]["stress"] == "axial_correspondence_slip" and pair[0]["level"] in SEVERE]
        row: Dict[str, Any] = {"attenuation_alpha": float(alpha)}
        for prefix, selected in [("open_control", oc), ("clean", clean), ("severe_stress", severe)]:
            for metric in METRICS:
                row[f"{prefix}_{metric}_relative_change"] = median_relative_change(selected, metric)
        row["severe_stress_axis_rmse_reduction"] = -row["severe_stress_axis_rmse_relative_change"]
        row["solver_failure_count"] = sum(int(pair[0]["solver_failure"]) for pair in pairs)
        row["feasible"] = bool(
            row["solver_failure_count"] == 0
            and row["open_control_trajectory_rmse_3d_relative_change"] <= 0.02
            and row["open_control_orientation_rmse_rad_relative_change"] <= 0.02
            and row["open_control_strong_translation_rmse_relative_change"] <= 0.02
            and row["clean_axis_rmse_relative_change"] <= 0.03
            and row["clean_strong_translation_rmse_relative_change"] <= 0.03
            and row["clean_orientation_rmse_rad_relative_change"] <= 0.03
            and row["severe_stress_strong_translation_rmse_relative_change"] <= 0.03
            and row["severe_stress_orientation_rmse_rad_relative_change"] <= 0.03
        )
        table.append(row)
    feasible = [row for row in table if row["feasible"]]
    if not feasible:
        return table, None
    best = max(float(row["severe_stress_axis_rmse_reduction"]) for row in feasible)
    selected = max(
        float(row["attenuation_alpha"])
        for row in feasible if float(row["severe_stress_axis_rmse_reduction"]) >= best - 0.01
    )
    for row in table:
        row["selected"] = float(row["attenuation_alpha"]) == selected
    return table, selected


def aggregate_method_trials(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["sweep"], row["level"], row["stress"], row["geometry_seed"], row["sensor_seed"], row["method"])].append(row)
    output = []
    for key, values in grouped.items():
        record = dict(zip(["sweep", "level", "stress", "geometry_seed", "sensor_seed", "method"], key))
        record["process_trial_count"] = len(values)
        for metric in METRICS:
            array = np.asarray([float(row[metric]) for row in values])
            record.update({
                f"{metric}_mean": float(np.mean(array)), f"{metric}_median": float(np.median(array)),
                f"{metric}_std": float(np.std(array)), f"{metric}_iqr": float(np.quantile(array, 0.75) - np.quantile(array, 0.25)),
                f"{metric}_q90": float(np.quantile(array, 0.90)), f"{metric}_q95": float(np.quantile(array, 0.95)),
            })
        output.append(record)
    return output


def build_paired_differences(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    indexed = index_rows(rows, include_method=True)
    output = []
    base_keys = sorted(set(key[:-1] for key in indexed))
    for key in base_keys:
        full = indexed[key + ("huber_full",)]
        for method in ["huber_selective", "huber_global", "huber_oracle_selective"]:
            candidate = indexed[key + (method,)]
            record = {name: value for name, value in zip(
                ["sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed"], key
            )}
            record["comparison"] = f"{method}_vs_huber_full"
            for metric in METRICS:
                record[f"{metric}_difference"] = float(candidate[metric]) - float(full[metric])
                record[f"{metric}_relative_change"] = relative_change(float(candidate[metric]), float(full[metric]))
            output.append(record)
    return output


def analyze_trial_results(rows: Sequence[Mapping[str, Any]], common: Mapping[str, Any]) -> Dict[str, Any]:
    indexed = index_rows(rows, include_method=True)
    contaminated = []
    per_geometry_effects = []
    for sweep in ["geometry", "observation"]:
        selected = [row for row in rows if row["sweep"] == sweep and row["stress"] == "axial_correspondence_slip" and row["level"] in SEVERE and row["method"] == "huber_selective"]
        effects = []
        protection = {metric: [] for metric in METRICS[1:]}
        global_axis = []
        global_strong = []
        for row in selected:
            key = trial_key(row)
            full = indexed[key + ("huber_full",)]
            global_row = indexed[key + ("huber_global",)]
            effects.append({"geometry_seed": row["geometry_seed"], "value": -relative_change(float(row["axis_rmse"]), float(full["axis_rmse"]))})
            for metric in METRICS[1:]:
                protection[metric].append(relative_change(float(row[metric]), float(full[metric])))
            global_axis.append(-relative_change(float(row["axis_rmse"]), float(global_row["axis_rmse"])))
            global_strong.append(-relative_change(float(row["strong_translation_rmse"]), float(global_row["strong_translation_rmse"])))
        bootstrap = block_bootstrap_effect(effects, int(common["bootstrap_repetitions"]), int(common["bootstrap_seed"]))
        for geometry_seed, value in bootstrap["per_geometry"].items():
            per_geometry_effects.append({
                "sweep": sweep,
                "geometry_seed": int(geometry_seed),
                "median_axis_rmse_reduction": float(value),
                "positive_improvement": bool(value > 0.0),
            })
        contaminated.append({
            "sweep": sweep, "median_axis_rmse_reduction": bootstrap["estimate"],
            "paired_mean_axis_rmse_reduction": float(np.mean([float(row["value"]) for row in effects])),
            "bootstrap_ci_low": bootstrap["ci_low"], "bootstrap_ci_high": bootstrap["ci_high"],
            "positive_improvement_geometry_ratio": bootstrap["positive_geometry_ratio"],
            "strong_translation_rmse_increase": float(np.median(protection["strong_translation_rmse"])),
            "orientation_rmse_rad_increase": float(np.median(protection["orientation_rmse_rad"])),
            "trajectory_rmse_3d_increase": float(np.median(protection["trajectory_rmse_3d"])),
            "selective_vs_global_axis_advantage": float(np.median(global_axis)),
            "selective_vs_global_strong_advantage": float(np.median(global_strong)),
        })
    clean = comparison_scope(rows, indexed, lambda row: row["stress"] == "clean")
    clean_by_level = comparison_scope_by_level(rows, indexed, lambda row: row["stress"] == "clean")
    open_control = comparison_scope(rows, indexed, lambda row: row["stress"] == "clean" and row["level"] == "OC", include_update=True)
    oracle = oracle_gap(rows, indexed)
    return {
        "tables": {
            "contaminated_severe_results": contaminated,
            "clean_noninferiority": clean,
            "clean_noninferiority_by_level": clean_by_level,
            "open_control_safety": open_control,
            "oracle_gap": oracle,
            "per_geometry_paired_effects": per_geometry_effects,
        }
    }


def comparison_scope(
    rows: Sequence[Mapping[str, Any]],
    indexed: Mapping[tuple, Mapping[str, Any]],
    predicate,
    include_update: bool = False,
) -> List[Dict[str, Any]]:
    selective = [row for row in rows if row["method"] == "huber_selective" and predicate(row)]
    output = {"scope_count": len(selective)}
    for metric in METRICS:
        output[f"{metric}_relative_change"] = float(np.median([
            relative_change(float(row[metric]), float(indexed[trial_key(row) + ("huber_full",)][metric]))
            for row in selective
        ]))
    if include_update:
        output["q95_update_norm_relative_change"] = float(np.median([
            relative_change(float(row["q95_update_norm"]), float(indexed[trial_key(row) + ("huber_full",)]["q95_update_norm"]))
            for row in selective
        ]))
        output["formal_actionable_rate"] = float(np.mean([float(row["actionable_rate"]) for row in selective]))
        output["solver_failure_count"] = sum(int(row["solver_failure"]) for row in selective)
    return [output]


def comparison_scope_by_level(
    rows: Sequence[Mapping[str, Any]],
    indexed: Mapping[tuple, Mapping[str, Any]],
    predicate,
) -> List[Dict[str, Any]]:
    selective = [row for row in rows if row["method"] == "huber_selective" and predicate(row)]
    grouped: Dict[tuple, List[Mapping[str, Any]]] = defaultdict(list)
    for row in selective:
        grouped[(row["sweep"], row["level"])].append(row)
    output = []
    for (sweep, level), values in sorted(grouped.items()):
        record: Dict[str, Any] = {"sweep": sweep, "level": level, "scope_count": len(values)}
        for metric in METRICS:
            record[f"{metric}_relative_change"] = float(np.median([
                relative_change(
                    float(row[metric]),
                    float(indexed[trial_key(row) + ("huber_full",)][metric]),
                )
                for row in values
            ]))
        output.append(record)
    return output


def oracle_gap(rows: Sequence[Mapping[str, Any]], indexed: Mapping[tuple, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    values = []
    for row in rows:
        if row["method"] != "huber_selective" or row["stress"] != "axial_correspondence_slip" or row["level"] not in SEVERE:
            continue
        key = trial_key(row)
        full = indexed[key + ("huber_full",)]
        oracle = indexed[key + ("huber_oracle_selective",)]
        gain_selective = float(full["axis_rmse"]) - float(row["axis_rmse"])
        gain_oracle = float(full["axis_rmse"]) - float(oracle["axis_rmse"])
        if gain_oracle > 0.0:
            values.append(gain_selective / gain_oracle)
    return [{"oracle_gain_capture_median": float(np.median(values)) if values else float("nan"), "eligible_pair_count": len(values)}]


def evaluate_stage2b_gates(
    rows: Sequence[Mapping[str, Any]], analyses: Mapping[str, Any],
    pairing_audit: Sequence[Mapping[str, Any]], stress_audit: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any], lock_checks: Mapping[str, Any], provenance: Mapping[str, Any],
) -> Dict[str, Any]:
    gates = common["gates"]
    contaminated_rows = analyses["tables"]["contaminated_severe_results"]
    contaminated_checks = {}
    for row in contaminated_rows:
        contaminated_checks[row["sweep"]] = bool(
            float(row["median_axis_rmse_reduction"]) >= float(gates["contaminated_axis_reduction_min"])
            and float(row["bootstrap_ci_low"]) > float(gates["contaminated_ci_low_min"])
            and float(row["positive_improvement_geometry_ratio"]) >= float(gates["positive_geometry_ratio_min"])
            and float(row["strong_translation_rmse_increase"]) <= float(gates["protected_increase_max"])
            and float(row["orientation_rmse_rad_increase"]) <= float(gates["protected_increase_max"])
            and float(row["trajectory_rmse_3d_increase"]) <= float(gates["protected_increase_max"])
            and float(row["selective_vs_global_strong_advantage"]) >= 0.0
            and (
                float(row["selective_vs_global_axis_advantage"]) >= float(gates["selective_vs_global_advantage_min"])
                or float(row["selective_vs_global_strong_advantage"]) >= float(gates["selective_vs_global_advantage_min"])
            )
        )
    clean = analyses["tables"]["clean_noninferiority"][0]
    clean_pass = all(
        float(clean[f"{metric}_relative_change"]) <= float(gates["clean_increase_max"])
        for metric in METRICS
    )
    control = analyses["tables"]["open_control_safety"][0]
    control_pass = bool(
        float(control["trajectory_rmse_3d_relative_change"]) <= float(gates["open_control_increase_max"])
        and float(control["strong_translation_rmse_relative_change"]) <= float(gates["open_control_increase_max"])
        and float(control["orientation_rmse_rad_relative_change"]) <= float(gates["open_control_increase_max"])
        and float(control["q95_update_norm_relative_change"]) <= float(gates["open_control_update_q95_increase_max"])
        and int(control["solver_failure_count"]) == 0
    )
    pairing_violations = sum(not bool(row["pairing_valid"]) for row in pairing_audit)
    solver_failures = sum(int(row["solver_failure"]) for row in rows)
    engineering_pass = bool(
        provenance.get("status") == "passed"
        and all(bool(lock_checks.get(name)) for name in [
            "source_hash_matched", "config_hash_matched", "stage2a_detector_artifact_matched",
            "stress_parameters_matched", "selected_alpha_matched", "seed_isolation_matched",
            "git_status_clean",
        ])
        and len({(row["sweep"], row["level"], row["stress"], row["geometry_seed"], row["sensor_seed"]) for row in rows}) == 360
        and len(rows) == 36000 and pairing_violations == 0 and solver_failures == 0
        and engineering_tests_present()
    )
    stress_pass = bool(stress_audit and all(bool(row["stress_mechanism_valid"]) for row in stress_audit))
    selective_pass = bool(
        engineering_pass and stress_pass and contaminated_checks.get("geometry", False)
        and contaminated_checks.get("observation", False) and clean_pass and control_pass
    )
    return {
        "engineering": "ENGINEERING_PASS" if engineering_pass else "ENGINEERING_FAIL",
        "stress_mechanism": "STRESS_MECHANISM_PASS" if stress_pass else "STRESS_MECHANISM_FAIL",
        "geometry_contaminated_severe": "PASS" if contaminated_checks.get("geometry", False) else "FAIL",
        "observation_contaminated_severe": "PASS" if contaminated_checks.get("observation", False) else "FAIL",
        "clean_noninferiority": "PASS" if clean_pass else "FAIL",
        "open_control_safety": "PASS" if control_pass else "FAIL",
        "selective_update": "SELECTIVE_UPDATE_PASS" if selective_pass else "SELECTIVE_UPDATE_FAIL",
        "checks": {"pairing_violations": pairing_violations, "solver_failures": solver_failures},
    }


def stage2b_authorizations(gates: Mapping[str, Any]) -> Dict[str, bool]:
    """Map the complete gate result to the only allowed downstream decisions."""

    passed = bool(gates.get("selective_update") == "SELECTIVE_UPDATE_PASS")
    return {
        "SELECTIVE_UPDATE_PASS": passed,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": passed,
        "RISK_WARNING_AUTHORIZED": False,
    }


def lock_update_analysis(root: Path, development_run_dir: Path) -> Dict[str, Any]:
    root = Path(root).resolve()
    run_dir = Path(development_run_dir).resolve()
    if (root / "results/weak_update_stage2b/development").resolve() not in run_dir.parents:
        raise ValueError("--lock-update accepts only a Stage 2B development run")
    output = run_dir / "update_lock.json"
    if output.exists():
        raise FileExistsError("update_lock.json is immutable and already exists")
    manifest = read_json(run_dir / "manifests/development_manifest.json")
    if manifest.get("status") != "OK" or manifest.get("selected_attenuation_alpha") is None:
        raise RuntimeError("DEVELOPMENT_NO_GO: no feasible locked alpha")
    common = load_yaml(root / "configs/update/stage2b_common.yaml")
    development = normalize_phase_config(load_yaml(root / "configs/update/stage2b_development.yaml"))
    reserved = normalize_phase_config(load_yaml(root / "configs/update/stage2b_test.yaml"))
    lock = build_update_lock(
        root, run_dir, manifest, read_json(run_dir / "online_odi_threshold.json"),
        read_csv(run_dir / "tables/alpha_selection.csv"), float(manifest["selected_attenuation_alpha"]),
        common, load_yaml(root / "configs/toy_lio/motion_surrogate_stage2b.yaml"),
        load_yaml(root / "configs/update/stage2b_stress.yaml"), development, reserved,
    )
    write_json(output, lock)
    frozen = root / "artifacts/current/weak_update_stage2b/locked/update_lock.json"
    frozen.parent.mkdir(parents=True, exist_ok=True)
    write_json(frozen, lock)
    return lock


def analyze_existing_stage2b(root: Path, run_dir: Path) -> Dict[str, Any]:
    manifests = list((Path(run_dir) / "manifests").glob("*_manifest.json"))
    if len(manifests) != 1:
        raise FileNotFoundError("analyze-only requires exactly one manifest")
    manifest = read_json(manifests[0])
    manifest.setdefault("analysis_history", []).append(analysis_record(Path(root)))
    write_json(manifests[0], manifest)
    return manifest


def build_manifest(
    root: Path, phase: str, run_id: str, data_run: Path, result_run: Path,
    phase_config: Mapping[str, Any], common: Mapping[str, Any], threshold: Mapping[str, Any],
    selected_alpha: float | None, rows: Sequence[Mapping[str, Any]], blocks: Sequence[Mapping[str, Any]],
    started: float, provenance: Mapping[str, Any] | None, lock_checks: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    return {
        "stage": "weak_subspace_update_stage2b", "phase": phase, "run_id": run_id,
        "status": "OK", "sensor_stress_block_count": len(blocks),
        "expected_sensor_stress_blocks": int(phase_config["expected_sensor_stress_blocks"]),
        "method_trial_count": len(rows), "expected_method_trials": int(phase_config["expected_method_trials"]),
        "selected_attenuation_alpha": selected_alpha,
        "online_odi_threshold": float(threshold["online_odi_threshold"]),
        "data_run_dir": relative(root, data_run), "result_run_dir": relative(root, result_run),
        "source_tree_sha256": compute_source_tree_hash(stage2b_source_paths(root)),
        "config_bundle_sha256": compute_bundle_hash(stage2b_config_paths(root)),
        "git_commit": git_commit(root), "git_status_clean_at_start": git_status_clean(root),
        "pytest_provenance": provenance, "lock_verification": lock_checks,
        "runtime_seconds": round(time.time() - started, 6), "analysis_history": [analysis_record(root)],
    }


def write_gate_outputs(result_run: Path, gates: Mapping[str, Any], authorizations: Mapping[str, bool], analyses: Mapping[str, Any]) -> None:
    rows = [{"gate": key, "status": value} for key, value in gates.items() if key != "checks"]
    rows.extend({"gate": key, "status": value} for key, value in authorizations.items())
    write_csv(result_run / "tables/gate_summary.csv", rows)
    lines = ["# Weak-Subspace Update Stage 2B Gate Report", ""]
    lines.extend(f"- {key}: **{value}**" for key, value in gates.items() if key != "checks")
    lines.extend(f"- {key}: **{str(value).lower()}**" for key, value in authorizations.items())
    lines.extend(["", "Oracle is an offline diagnostic only. Stage 2B does not integrate FAST-LIO2, use real IMU propagation, implement real data association, or reopen risk prediction.", ""])
    (result_run / "reports/weak_update_stage2b_gate_report.md").write_text("\n".join(lines), encoding="utf-8")
    (result_run / "reports/weak_update_stage2b_reproducibility_report.md").write_text(
        "# Stage 2B Reproducibility\n\nTest used a committed update lock, disjoint seeds, shared observations/process noise/stress, and frozen alpha.\n",
        encoding="utf-8",
    )


def build_development_report(alpha: float, threshold: Mapping[str, Any], alpha_rows: Sequence[Mapping[str, Any]], blocks: int, trials: int) -> str:
    return (
        "# Stage 2B Development Report\n\n"
        f"- Sensor-stress blocks: {blocks}\n- Saved method trials: {trials}\n"
        f"- Motion-prior Open Control ODI threshold: {threshold['online_odi_threshold']}\n"
        f"- Selected attenuation alpha: {alpha}\n\nReserved test seeds were not evaluated.\n"
    )


def export_current_artifacts(root: Path, result_run: Path, lock_path: Path, manifest: Mapping[str, Any]) -> None:
    target = root / "artifacts/current/weak_update_stage2b"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lock_path, target / "update_lock.json")
    for relative_path in [
        "reports/weak_update_stage2b_gate_report.md", "reports/weak_update_stage2b_reproducibility_report.md",
        "tables/contaminated_severe_results.csv", "tables/clean_noninferiority.csv",
        "tables/open_control_safety.csv", "tables/oracle_gap.csv", "tables/gate_summary.csv",
    ]:
        source = result_run / relative_path
        shutil.copy2(source, target / source.name)
    write_json(target / "test_manifest.json", manifest)


def generate_figures(result_run: Path, rows: Sequence[Mapping[str, Any]], alpha_rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_names = [
        "axis_rmse_severe_contaminated", "strong_rmse_severe_contaminated", "open_control_safety",
        "selective_vs_global_paired", "selective_vs_huber_paired", "oracle_gap",
        "alpha_development_tradeoff", "trigger_and_update_timeline_examples",
    ]
    for index, name in enumerate(figure_names):
        fig, axis = plt.subplots(figsize=(6, 4))
        if name == "alpha_development_tradeoff" and alpha_rows:
            axis.plot([float(row["attenuation_alpha"]) for row in alpha_rows], [float(row["severe_stress_axis_rmse_reduction"]) for row in alpha_rows], marker="o")
            axis.set_xlabel("attenuation alpha")
            axis.set_ylabel("median axis RMSE reduction")
        else:
            selected = [row for row in rows if row["method"] in {"huber_full", "huber_selective", "huber_global", "huber_oracle_selective"}][:400]
            x = np.arange(len(selected))
            y = [float(row["axis_rmse"] if "axis" in name or "oracle" in name else row["strong_translation_rmse"]) for row in selected]
            colors = ["tab:purple" if row["method"] == "huber_oracle_selective" else "tab:blue" for row in selected]
            axis.scatter(x, y, c=colors, s=8, alpha=0.6)
            axis.set_xlabel("paired independent-block samples")
            axis.set_ylabel("RMSE")
        axis.set_title(name.replace("_", " "))
        fig.tight_layout()
        fig.savefig(result_run / f"figures/{name}.png", dpi=150)
        plt.close(fig)


def audit_method_pairing(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[trial_key(row)].append(row)
    output = []
    for key, values in grouped.items():
        checks = {
            field: len({str(row[field]) for row in values}) == 1
            for field in [
                "observation_checksum", "stress_checksum", "process_noise_checksum",
                "initial_state_checksum", "initial_covariance_checksum",
            ]
        }
        methods_complete = {row["method"] for row in values} == set(METHODS)
        output.append({
            **{name: value for name, value in zip(["sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed"], key)},
            **checks, "methods_complete": methods_complete,
            "pairing_valid": methods_complete and all(checks.values()),
        })
    return output


def stress_mechanism_audit(
    spec: Mapping[str, Any], sensor_seed: int, stress_name: str,
    clean: Mapping[str, np.ndarray], stressed: Mapping[str, np.ndarray],
    patch_ids: np.ndarray, stress_config: Mapping[str, Any],
) -> Dict[str, Any]:
    mask = np.asarray(stressed["contamination_mask"], dtype=bool)
    axial = np.asarray(clean["is_axial_support"], dtype=bool)
    clean_unchanged = bool(stress_name != "clean" or (
        not np.any(mask) and np.array_equal(clean["plane_points_world"], stressed["plane_points_world"])
    ))
    open_zero = bool(spec["level"] != "OC" or not np.any(mask))
    axial_only = bool(not np.any(mask) or np.all(axial[mask]))
    variance_unchanged = np.array_equal(clean["R_diag_list"], stressed["R_diag_list"])
    invariant_observations_unchanged = all(
        np.array_equal(clean[field], stressed[field])
        for field in ["points_lidar", "normals_world", "r_list", "R_diag_list"]
    )
    expected_anchor_delta = (
        np.asarray(stressed["contamination_offset_m"], dtype=float)[..., None]
        * np.asarray(clean["normals_world"], dtype=float)
    )
    locked_anchor_delta = bool(np.allclose(
        np.asarray(stressed["plane_points_world"], dtype=float)
        - np.asarray(clean["plane_points_world"], dtype=float),
        expected_anchor_delta,
        atol=1.0e-12,
        rtol=0.0,
    ))
    selected = np.asarray(stressed["contaminated_patch_ids"]).astype(str).tolist()
    starts = np.asarray(stressed["contaminated_patch_burst_start_frames"], dtype=int)
    signs = np.asarray(stressed["contaminated_patch_burst_signs"], dtype=int)
    configured_duration = (
        0 if stress_name == "clean"
        else int(stress_config["stress_regimes"][stress_name]["burst_length_frames"])
    )
    duration_valid = bool(
        len(selected) == starts.size == signs.size
        and (not selected or configured_duration == 8)
        and np.all(starts >= 0)
        and np.all(starts + configured_duration <= mask.shape[0])
        and np.all(np.isin(signs, [-1, 1]))
    )
    # A selected patch can be absent from a particular retained scan.  For every
    # observed contaminated sample, however, the active frames must be inside
    # that patch's locked eight-frame burst.
    for patch, start in zip(selected, starts):
        frames = np.flatnonzero(np.any(mask & (patch_ids == patch), axis=1))
        duration_valid &= bool(
            not frames.size
            or np.all((frames >= start) & (frames < start + configured_duration))
        )
    residual_ratio = 1.0
    if np.any(mask):
        clean_abs = np.abs(np.asarray(clean["r_list"])[mask])
        stressed_abs = np.abs(np.asarray(clean["r_list"])[mask] - np.asarray(stressed["contamination_offset_m"])[mask])
        residual_ratio = float(np.mean(stressed_abs) / max(np.mean(clean_abs), 1.0e-12))
    residual_higher = bool(not np.any(mask) or residual_ratio > 1.5)
    valid = bool(
        clean_unchanged and open_zero and axial_only and duration_valid
        and variance_unchanged and invariant_observations_unchanged
        and locked_anchor_delta and residual_higher
    )
    return {
        "sweep": sweep_name(spec), "level": spec["level"], "stress": stress_name,
        "geometry_seed": spec["geometry_seed"], "sensor_seed": int(sensor_seed),
        "configured_burst_length_frames": configured_duration,
        "contaminated_measurement_count": int(np.sum(mask)),
        "clean_unchanged": clean_unchanged, "open_control_contamination_zero": open_zero,
        "axial_only": axial_only, "burst_duration_valid": duration_valid,
        "variance_unchanged": variance_unchanged,
        "invariant_observations_unchanged": invariant_observations_unchanged,
        "locked_anchor_delta": locked_anchor_delta,
        "contaminated_residual_ratio": residual_ratio,
        "stress_mechanism_valid": valid,
    }


def observation_checksum(observations: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for field in ["points_lidar", "normals_world", "plane_points_world", "r_list", "R_diag_list", "is_axial_support"]:
        digest.update(field.encode("utf-8")); digest.update(array_checksum(np.asarray(observations[field])).encode("ascii"))
    return digest.hexdigest()


def sweep_name(spec: Mapping[str, Any]) -> str:
    if spec["level"] == "OC":
        return "open_control"
    return str(spec["sweep_type"])


def trial_key(row: Mapping[str, Any]) -> tuple:
    return tuple(row[field] for field in ["sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed"])


def index_rows(rows: Sequence[Mapping[str, Any]], include_method: bool = False) -> Dict[tuple, Mapping[str, Any]]:
    output = {}
    for row in rows:
        key = trial_key(row) + ((row["method"],) if include_method else ())
        output[key] = row
    return output


def relative_change(candidate: float, baseline: float) -> float:
    return (float(candidate) - float(baseline)) / max(abs(float(baseline)), 1.0e-12)


def median_relative_change(pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]], metric: str) -> float:
    if not pairs:
        return float("nan")
    return float(np.median([relative_change(float(left[metric]), float(right[metric])) for left, right in pairs]))


def block_bootstrap_effect(effects: Sequence[Mapping[str, Any]], repetitions: int, seed: int) -> Dict[str, Any]:
    grouped: Dict[int, List[float]] = defaultdict(list)
    for row in effects:
        grouped[int(row["geometry_seed"])].append(float(row["value"]))
    seeds = sorted(grouped)
    per_geometry = {key: float(np.median(grouped[key])) for key in seeds}
    estimate = float(np.median([row["value"] for row in effects]))
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(repetitions):
        sampled = rng.choice(seeds, size=len(seeds), replace=True)
        values = [value for geometry in sampled for value in grouped[int(geometry)]]
        samples.append(float(np.median(values)))
    return {
        "estimate": estimate, "ci_low": float(np.quantile(samples, 0.025)),
        "ci_high": float(np.quantile(samples, 0.975)),
        "positive_geometry_ratio": float(np.mean([value > 0.0 for value in per_geometry.values()])),
        "per_geometry": per_geometry,
    }


def engineering_tests_present() -> bool:
    root = Path(__file__).resolve().parents[2]
    required = [
        "tests/test_prior_relinearization.py", "tests/test_stage2b_no_gt_dependency.py",
        "tests/test_covariance_propagation.py", "tests/test_selective_update_psd.py",
        "tests/test_selective_alpha_one_equivalence.py", "tests/test_selective_nontrigger_equivalence.py",
    ]
    return all((root / path).exists() for path in required)


def analysis_record(root: Path) -> Dict[str, Any]:
    return {
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_git_commit": git_commit(root),
        "analysis_source_tree_sha256": compute_source_tree_hash(stage2b_source_paths(root)),
    }
