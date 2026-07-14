"""Stage 1c independent confirmatory validation.

Stage 1c freezes the Stage 1b metric definitions, separates development from
reserved test seeds, and refuses test generation unless the committed source,
configuration bundle, analysis lock, and two real pytest provenance records
match. It does not implement an estimator update.
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
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
from scipy.stats import kendalltau

from degen_detector.exposure_metrics import summarize_exposure_metrics
from degen_detector.odi_tracker import compute_metrics_for_sequence
from eval.analysis_lock import (
    METRIC_DEFINITION_VERSION,
    build_analysis_lock,
    calibrate_low_information_threshold,
    compute_bundle_hash,
    compute_source_tree_hash,
    git_commit,
    git_path_commit,
    git_status_clean,
    sha256_file,
    stage1c_config_paths,
    stage1c_source_paths,
    utc_now,
    verify_analysis_lock,
)
from eval.hierarchical_statistics import (
    block_bootstrap_spearman,
    paired_monotonicity,
    safe_spearman,
)
from eval.synthetic_pipeline_common import (
    aggregate_process_targets,
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
    write_structured_csv,
)
from eval.test_provenance import validate_test_provenance
from minibench.motion_simulator import (
    process_noise_checksum,
    save_motion_measurements,
    simulate_motion_measurements,
)
from minibench.toy_lio import load_toy_lio_config, resolve_process_noise_parameters, run_toy_lio, save_pose_est_tum


LEVEL_ORDERS = {"geometry": ["L1", "L2", "L3", "L4"], "observation": ["O1", "O2", "O3", "O4"]}
NOISE_FAMILIES = {
    ("geometry", "ST"): "stage1c_geometry",
    ("observation", "ST"): "stage1c_observation",
    ("geometry", "OC"): "stage1c_open_control",
}


def run_stage1c(
    root: Path,
    phase: str,
    run_id: str,
    common_config_path: Path,
    phase_config_path: Path,
    detector_config_path: Path,
    motion_config_path: Path,
    workers: int = 1,
    resume: bool = False,
    overwrite: bool = False,
    analysis_lock_path: Path | None = None,
) -> Dict[str, Any]:
    if phase not in {"quick", "development", "test"}:
        raise ValueError(f"Unsupported Stage 1c phase: {phase}")
    if not run_id:
        raise ValueError("Stage 1c requires an explicit run_id")
    if workers < 1:
        raise ValueError("workers must be positive")
    root = Path(root).resolve()
    common = load_yaml(common_config_path)
    phase_config = normalize_phase_config(load_yaml(phase_config_path))
    detector = load_yaml(detector_config_path)
    motion_raw = load_yaml(motion_config_path)
    validate_phase_seed_contract(root, phase, phase_config)

    lock: Dict[str, Any] | None = None
    lock_verification: Dict[str, Any] | None = None
    provenance_validation: Dict[str, Any] | None = None
    if phase == "test":
        if analysis_lock_path is None or not Path(analysis_lock_path).exists():
            raise RuntimeError("REFUSE_TEST_EXECUTION: --analysis-lock is required and must exist")
        lock = read_json(Path(analysis_lock_path))
        lock_verification = verify_analysis_lock(root, lock, require_clean=True)
        validate_reserved_test_seeds(phase_config, lock)
        provenance_paths = [
            root / "results/metric_redesign_stage1c/test_provenance_run1.json",
            root / "results/metric_redesign_stage1c/test_provenance_run2.json",
        ]
        if not all(path.exists() for path in provenance_paths):
            raise RuntimeError("REFUSE_TEST_EXECUTION: two verified pytest provenance files are required")
        provenance_records = [read_json(path) for path in provenance_paths]
        provenance_validation = validate_test_provenance(
            provenance_records,
            git_commit(root),
            str(lock["source_tree_sha256"]),
        )
        if not provenance_validation["all_valid"]:
            raise RuntimeError(f"REFUSE_TEST_EXECUTION: invalid pytest provenance {provenance_validation}")

    started = time.time()
    data_run = root / "data/metric_redesign_stage1c" / phase / run_id
    result_run = root / "results/metric_redesign_stage1c" / phase / run_id
    prepare_run_directories(data_run, result_run, resume=resume, overwrite=overwrite)
    for name in ["tables", "reports", "manifests", "sensors", "trials", "trajectories", "motion"]:
        (result_run / name).mkdir(parents=True, exist_ok=True)
    config_hash = compute_bundle_hash(stage1c_config_paths(root))
    source_hash = compute_source_tree_hash(stage1c_source_paths(root))
    generation_started = utc_now()
    specs = build_stage1c_specs(common, phase_config, phase)
    process_seeds = list(phase_config["process_seeds"])
    sensor_seeds = list(phase_config["sensor_seeds"])
    motion_config = load_toy_lio_config(motion_raw)

    process_rows: List[Dict[str, Any]] = []
    sensor_base_rows: List[Dict[str, Any]] = []
    for spec in specs:
        sequence_dir = data_run / str(spec["sequence_id"])
        generate_or_validate_sequence(sequence_dir, spec)
        for sensor_seed in sensor_seeds:
            sensor_dir = sequence_dir / f"sensor_{sensor_seed:03d}"
            sensor_record = result_run / "sensors" / str(spec["sequence_id"]) / f"sensor_{sensor_seed:03d}.json"
            trial_paths = [trial_json_path(result_run, spec, sensor_seed, seed) for seed in process_seeds]
            complete = sensor_record.exists() and all(path.exists() for path in trial_paths)
            observations: Dict[str, np.ndarray] | None = None
            if complete and resume:
                base = read_json(sensor_record)
            else:
                observations = generate_or_load_observations(
                    sensor_dir,
                    sequence_dir,
                    spec,
                    detector_config_path,
                    {"candidate_multiplier": int(common["observation_candidate_multiplier"])},
                    int(sensor_seed),
                    resume,
                )
                metrics = compute_metrics_for_sequence(observations, detector)
                write_structured_csv(metrics, sensor_dir / "metrics.csv")
                base = build_sensor_base_row(root, sequence_dir, sensor_dir, spec, int(sensor_seed), observations, metrics)
                write_json(sensor_record, base)
            sensor_base_rows.append(dict(base))
            missing = [seed for seed, path in zip(process_seeds, trial_paths) if not (resume and path.exists())]
            if missing:
                if observations is None:
                    observations = load_npz(sensor_dir / "observations.npz")
                rows = run_sensor_process_trials(
                    root,
                    result_run,
                    sequence_dir,
                    spec,
                    int(sensor_seed),
                    observations,
                    detector,
                    motion_config,
                    motion_raw,
                    missing,
                    workers,
                )
                for row in rows:
                    write_json(trial_json_path(result_run, spec, sensor_seed, int(row["process_seed"])), row)
            process_rows.extend(read_json(path) for path in trial_paths)

    calibration = resolve_phase_threshold(
        root,
        phase,
        data_run,
        sensor_base_rows,
        common,
        lock,
        result_run,
    )
    sensor_base_rows = add_exposure_metrics(root, sensor_base_rows, calibration, common)
    sensor_rows = merge_sensor_process_summaries(sensor_base_rows, process_rows)
    write_csv(result_run / "tables/process_trial_summary.csv", process_rows)
    write_csv(result_run / "tables/sensor_run_summary.csv", sensor_rows)
    noise_audit = build_process_noise_audit(process_rows, int(phase_config["expected_unique_noise_sequences"]))
    write_csv(result_run / "tables/process_noise_audit.csv", noise_audit["rows"])

    data_generation = {
        "started_at": generation_started,
        "finished_at": utc_now(),
        "data_generation_git_commit": git_commit(root),
        "data_generation_source_tree_sha256": source_hash,
        "config_bundle_sha256": config_hash,
        "git_status_clean_at_start": git_status_clean(root),
    }
    manifest: Dict[str, Any] = {
        "stage": "metric_redesign_stage1c",
        "phase": phase,
        "run_id": run_id,
        "status": "GENERATED",
        "data_run_dir": relative(root, data_run),
        "result_run_dir": relative(root, result_run),
        "data_generation": data_generation,
        "analysis_history": [],
        "test_provenance": None,
        "sensor_run_count": len(sensor_rows),
        "process_trial_count": len(process_rows),
        "unique_process_noise_sequences": noise_audit["actual_unique_noise_sequences"],
        "process_noise_pairing_violations": noise_audit["pairing_violations"],
        "process_noise_independence_violations": noise_audit["independence_violations"],
        "low_information_ratio_unique_count": unique_finite_count(sensor_rows, "low_axis_information_ratio"),
        "longest_low_information_duration_unique_count": unique_finite_count(
            sensor_rows, "longest_low_information_duration_s"
        ),
        "analysis_lock_sha256": sha256_file(Path(analysis_lock_path)) if analysis_lock_path else None,
        "analysis_lock_path": relative(root, Path(analysis_lock_path)) if analysis_lock_path else None,
        "config_bundle_sha256": config_hash,
        "data_generation_git_commit": data_generation["data_generation_git_commit"],
        "data_generation_source_tree_sha256": source_hash,
        "analysis_git_commit": None,
        "analysis_source_tree_sha256": None,
        "test_execution_git_commit": git_commit(root) if phase == "test" else None,
        "test_source_tree_sha256": source_hash if phase == "test" else None,
    }
    manifest["analysis_git_commit"] = git_commit(root)
    manifest["analysis_source_tree_sha256"] = compute_source_tree_hash(stage1c_source_paths(root))
    if phase == "test":
        lock_artifact_commit = git_path_commit(root, Path(analysis_lock_path))
        manifest["test_provenance"] = {
            "analysis_lock_commit": lock_artifact_commit,
            "analysis_source_commit_at_lock": lock["git_commit_at_lock"] if lock else None,
            "test_execution_commit": git_commit(root),
            "source_hash_matched": lock_verification["source_hash_matched"] if lock_verification else False,
            "config_hash_matched": lock_verification["config_hash_matched"] if lock_verification else False,
            "pytest_provenance": provenance_validation,
        }
    write_json(result_run / f"manifests/{phase}_manifest.json", manifest)
    analysis = analyze_stage1c_run(root, result_run, sensor_rows, process_rows, common, phase, manifest, lock)
    manifest.update(
        {
            "status": "OK" if analysis["counts_match"] else "INCOMPLETE",
            "runtime_seconds": round(time.time() - started, 6),
            "gates": analysis.get("gates"),
            "authorizations": analysis.get("authorizations"),
        }
    )
    append_analysis_history(manifest, root)
    write_json(result_run / f"manifests/{phase}_manifest.json", manifest)
    return manifest


def normalize_phase_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    output = dict(config)
    process = output["process_seeds"]
    if isinstance(process, Mapping):
        start = int(process["start"])
        output["process_seeds"] = list(range(start, start + int(process["count"])))
    else:
        output["process_seeds"] = [int(value) for value in process]
    output["geometry_seeds"] = [int(value) for value in output["geometry_seeds"]]
    output["sensor_seeds"] = [int(value) for value in output["sensor_seeds"]]
    return output


def validate_phase_seed_contract(root: Path, phase: str, phase_config: Mapping[str, Any]) -> None:
    development = normalize_phase_config(load_yaml(root / "configs/redesign/stage1c_development.yaml"))
    reserved = normalize_phase_config(load_yaml(root / "configs/redesign/stage1c_test.yaml"))
    for field in ["geometry_seeds", "sensor_seeds", "process_seeds"]:
        if set(development[field]) & set(reserved[field]):
            raise ValueError(f"Stage 1c development/test {field} overlap")
    if phase == "test":
        if list(phase_config["geometry_seeds"]) != list(reserved["geometry_seeds"]):
            raise RuntimeError("REFUSE_TEST_EXECUTION: reserved geometry seeds changed")
        if list(phase_config["sensor_seeds"]) != [33, 44]:
            raise RuntimeError("REFUSE_TEST_EXECUTION: test sensor seeds must be 33 and 44")
        if list(phase_config["process_seeds"]) != list(range(2001, 2031)):
            raise RuntimeError("REFUSE_TEST_EXECUTION: test process seeds must be 2001-2030")


def validate_reserved_test_seeds(test_config: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    comparisons = [
        ("geometry_seeds", "reserved_test_geometry_seeds"),
        ("sensor_seeds", "reserved_test_sensor_seeds"),
        ("process_seeds", "reserved_test_process_seeds"),
    ]
    for config_key, lock_key in comparisons:
        if list(test_config[config_key]) != list(lock[lock_key]):
            raise RuntimeError(f"REFUSE_TEST_EXECUTION: {config_key} does not match analysis lock")


def prepare_run_directories(data_run: Path, result_run: Path, resume: bool, overwrite: bool) -> None:
    existing = [path for path in [data_run, result_run] if path.exists()]
    if existing and overwrite:
        for path in existing:
            shutil.rmtree(path)
    elif existing and not resume:
        raise FileExistsError("Stage 1c run exists; use --resume or --overwrite for this run only")
    data_run.mkdir(parents=True, exist_ok=True)
    result_run.mkdir(parents=True, exist_ok=True)


def build_stage1c_specs(
    common: Mapping[str, Any], phase_config: Mapping[str, Any], phase: str
) -> List[Dict[str, Any]]:
    scene = common["scene"]
    specs: List[Dict[str, Any]] = []
    for geometry_seed in phase_config["geometry_seeds"]:
        oc = make_spec(scene, "geometry", "OC", int(geometry_seed), phase, scene_family="OC", active_patch_count=0)
        oc["sequence_id"] = f"stage1c_{phase}_open_control_G{geometry_seed}"
        oc["experiment_family"] = "stage1c_open_control"
        specs.append(oc)
        for level, count in common["geometry_levels"].items():
            spec = make_spec(
                scene, "geometry", str(level), int(geometry_seed), phase, active_patch_count=int(count)
            )
            spec["sequence_id"] = f"stage1c_{phase}_geometry_{level}_G{geometry_seed}"
            spec["experiment_family"] = "stage1c_geometry"
            specs.append(spec)
        for level, probability in common["observation_levels"].items():
            spec = make_spec(
                scene,
                "observation",
                str(level),
                int(geometry_seed),
                phase,
                active_patch_count=int(scene["master_axial_patch_pool_size"]),
                keep_probability=float(probability),
            )
            spec["sequence_id"] = f"stage1c_{phase}_observation_{level}_G{geometry_seed}"
            spec["experiment_family"] = "stage1c_observation"
            specs.append(spec)
    return specs


def build_sensor_base_row(
    root: Path,
    sequence_dir: Path,
    sensor_dir: Path,
    spec: Mapping[str, Any],
    sensor_seed: int,
    observations: Mapping[str, np.ndarray],
    metrics: np.ndarray,
) -> Dict[str, Any]:
    metadata = read_json(sequence_dir / "scene_metadata.json")
    axial = np.asarray(observations.get("is_axial_support", np.zeros_like(observations["r_list"], dtype=bool)))
    row: Dict[str, Any] = {
        "phase": spec["split"],
        "sweep_type": spec["sweep_type"],
        "experiment_family": spec["experiment_family"],
        "sequence_id": spec["sequence_id"],
        "level": spec["level"],
        "scene_family": spec["scene_family"],
        "geometry_seed": int(spec["geometry_seed"]),
        "sensor_seed": int(sensor_seed),
        "geometry_axial_support_score": float(metadata.get("geometry_axial_support_score", 0.0)),
        "active_axial_patch_count": int(metadata.get("active_axial_patch_count", 0)),
        "active_patch_ids": ";".join(metadata.get("active_patch_ids", [])),
        "non_axial_shell_checksum": metadata.get("non_axial_shell_checksum", "open_control"),
        "sampling_weight_checksum": metadata.get("sampling_weight_checksum", "open_control"),
        "gt_checksum": metadata["gt_checksum"],
        "planes_checksum": metadata["planes_checksum"],
        "axis_checksum": metadata["axis_checksum"],
        "geometry_metadata_checksum": metadata["geometry_metadata_checksum"],
        "axial_observation_keep_probability": float(spec.get("axial_observation_keep_probability", 1.0)),
        "requested_points_per_frame": int(observations["packed_J"].shape[1]),
        "realized_total_points": int(axial.size),
        "realized_axial_points": int(np.sum(axial)),
        "realized_non_axial_points": int(axial.size - np.sum(axial)),
        "realized_axial_point_fraction": float(np.mean(axial)),
        "metrics_path": relative(root, sensor_dir / "metrics.csv"),
        "observations_path": relative(root, sensor_dir / "observations.npz"),
    }
    if "candidate_uniforms" in observations:
        row.update(
            {
                "candidate_uniform_checksum": array_sha256(observations["candidate_uniforms"]),
                "candidate_axial_checksum": array_sha256(observations["candidate_is_axial"]),
                "retained_axial_checksum": array_sha256(observations["retained_axial_candidate_mask"]),
            }
        )
    else:
        row.update(
            {
                "candidate_uniform_checksum": "not_applicable",
                "candidate_axial_checksum": "not_applicable",
                "retained_axial_checksum": "not_applicable",
            }
        )
    for field in [
        "ODI_trans",
        "axis_information_normalized",
        "weak_trans_subspace_alignment",
    ]:
        values = np.asarray(metrics[field], dtype=float)
        finite = values[np.isfinite(values)]
        row[f"{field}_median"] = float(np.median(finite)) if finite.size else float("nan")
        row[f"{field}_p10"] = float(np.percentile(finite, 10.0)) if finite.size else float("nan")
        row[f"{field}_p90"] = float(np.percentile(finite, 90.0)) if finite.size else float("nan")
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
    experiment_family = str(spec["experiment_family"])
    parameters = resolve_process_noise_parameters(family, motion_config)
    profile = str(motion_raw["motion_profile_id"])
    motions: Dict[int, Dict[str, np.ndarray]] = {}
    for process_seed in process_seeds:
        motion = simulate_motion_measurements(
            observations["pose_gt"],
            int(process_seed),
            parameters,
            axes=observations["axis_per_frame"],
            motion_profile_id=profile,
            experiment_family=experiment_family,
            geometry_seed=int(spec["geometry_seed"]),
            sensor_seed=int(sensor_seed),
        )
        motions[int(process_seed)] = motion
        path = (
            result_run
            / "motion"
            / experiment_family
            / f"G{int(spec['geometry_seed'])}"
            / f"sensor_{sensor_seed:03d}"
            / f"process_{process_seed}.npz"
        )
        if not path.exists():
            save_motion_measurements(motion, path)

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
        trajectory = (
            result_run
            / "trajectories"
            / str(spec["sequence_id"])
            / f"sensor_{sensor_seed:03d}"
            / f"process_{process_seed}.tum"
        )
        save_pose_est_tum(result["poses"], trajectory)
        row: Dict[str, Any] = {
            "phase": spec["split"],
            "sweep_type": spec["sweep_type"],
            "experiment_family": experiment_family,
            "sequence_id": spec["sequence_id"],
            "level": spec["level"],
            "scene_family": family,
            "geometry_seed": int(spec["geometry_seed"]),
            "sensor_seed": int(sensor_seed),
            "process_seed": int(process_seed),
            "motion_profile_id": profile,
            "process_noise_seed_resolved": int(np.asarray(motion["process_noise_seed_resolved"]).item()),
            "process_noise_checksum": process_noise_checksum(motion),
            "trajectory_path": relative(root, trajectory),
        }
        row.update({key: float(value) for key, value in result["summary"].items()})
        return row

    if workers == 1 or len(process_seeds) == 1:
        return [execute(seed) for seed in process_seeds]
    with ThreadPoolExecutor(max_workers=min(workers, len(process_seeds))) as executor:
        return list(executor.map(execute, process_seeds))


def resolve_phase_threshold(
    root: Path,
    phase: str,
    data_run: Path,
    sensor_rows: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any],
    lock: Mapping[str, Any] | None,
    result_run: Path,
) -> Dict[str, Any]:
    if phase == "test":
        if lock is None or "low_axis_information_threshold" not in lock:
            raise RuntimeError("REFUSE_TEST_EXECUTION: locked low-information threshold is missing")
        return {
            "low_information_quantile": float(lock["low_information_quantile"]),
            "low_axis_information_threshold": float(lock["low_axis_information_threshold"]),
            "calibration_source": "development_open_control_only",
            "calibration_frame_count": int(lock["calibration_frame_count"]),
            "calibration_data_hash": str(lock["calibration_data_hash"]),
            "metric_definition_version": str(lock["metric_definition_version"]),
        }
    values: List[float] = []
    for row in sensor_rows:
        if str(row["scene_family"]) != "OC":
            continue
        metric_rows = read_csv(root / str(row["metrics_path"]))
        values.extend(float(metric["axis_information_normalized"]) for metric in metric_rows)
    quantile = float(common["analysis"]["low_information_quantile"])
    threshold = calibrate_low_information_threshold(values, quantile)
    value_array = np.asarray(values, dtype=float)
    calibration = {
        "low_information_quantile": quantile,
        "low_axis_information_threshold": threshold,
        "calibration_source": "development_open_control_only",
        "calibration_frame_count": int(value_array.size),
        "calibration_data_hash": array_sha256(value_array),
        "metric_definition_version": METRIC_DEFINITION_VERSION,
    }
    write_json(result_run / "threshold_calibration.json", calibration)
    write_csv(result_run / "tables/threshold_calibration.csv", [calibration])
    return calibration


def add_exposure_metrics(
    root: Path,
    sensor_rows: Sequence[Mapping[str, Any]],
    calibration: Mapping[str, Any],
    common: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    output = []
    for source in sensor_rows:
        row = dict(source)
        metric_rows = read_csv(root / str(row["metrics_path"]))
        exposure = summarize_exposure_metrics(
            metric_rows,
            float(calibration["low_axis_information_threshold"]),
            float(common["analysis"]["exposure_epsilon"]),
            float(common["analysis"]["weak_axis_alignment_threshold"]),
        )
        row.update(exposure)
        row["low_axis_information_threshold"] = float(calibration["low_axis_information_threshold"])
        output.append(row)
    return output


def merge_sensor_process_summaries(
    base_rows: Sequence[Mapping[str, Any]], process_rows: Sequence[Mapping[str, Any]]
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, int], List[Mapping[str, Any]]] = defaultdict(list)
    for row in process_rows:
        grouped[(str(row["sequence_id"]), int(row["sensor_seed"]))].append(row)
    output = []
    for source in base_rows:
        row = dict(source)
        row.update(aggregate_process_targets(grouped[(str(row["sequence_id"]), int(row["sensor_seed"]))]))
        output.append(row)
    return output


def build_process_noise_audit(
    process_rows: Sequence[Mapping[str, Any]], expected_unique: int
) -> Dict[str, Any]:
    pairing: Dict[Tuple[str, int, int, int], set[str]] = defaultdict(set)
    seed_by_unit: Dict[Tuple[str, int, int, int], set[int]] = defaultdict(set)
    audit_rows = []
    for row in process_rows:
        key = (
            str(row["experiment_family"]),
            int(row["geometry_seed"]),
            int(row["sensor_seed"]),
            int(row["process_seed"]),
        )
        pairing[key].add(str(row["process_noise_checksum"]))
        seed_by_unit[key].add(int(row["process_noise_seed_resolved"]))
        audit_rows.append(
            {
                "experiment_family": row["experiment_family"],
                "geometry_seed": row["geometry_seed"],
                "sensor_seed": row["sensor_seed"],
                "level": row["level"],
                "process_seed": row["process_seed"],
                "process_noise_seed_resolved": row["process_noise_seed_resolved"],
                "process_noise_checksum": row["process_noise_checksum"],
            }
        )
    pairing_violations = sum(
        len(pairing[key]) != 1 or len(seed_by_unit[key]) != 1 for key in pairing
    )
    unit_checksums = [next(iter(values)) for values in pairing.values() if len(values) == 1]
    actual_unique = len(set(unit_checksums))
    independence_violations = max(0, len(seed_by_unit) - actual_unique)
    return {
        "rows": audit_rows,
        "expected_unique_noise_sequences": int(expected_unique),
        "actual_unique_noise_sequences": actual_unique,
        "pairing_violations": pairing_violations,
        "independence_violations": independence_violations,
    }


def trial_json_path(result_run: Path, spec: Mapping[str, Any], sensor_seed: int, process_seed: int) -> Path:
    return (
        result_run
        / "trials"
        / str(spec["sequence_id"])
        / f"sensor_{sensor_seed:03d}"
        / f"process_{process_seed}.json"
    )


def analyze_stage1c_run(
    root: Path,
    result_run: Path,
    sensor_rows: Sequence[Mapping[str, Any]],
    process_rows: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any],
    phase: str,
    manifest: Mapping[str, Any],
    lock: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    phase_config = normalize_phase_config(load_yaml(root / f"configs/redesign/stage1c_{phase}.yaml"))
    counts_match = (
        len(sensor_rows) == int(phase_config["expected_sensor_runs"])
        and len(process_rows) == int(phase_config["expected_process_trials"])
    )
    level_summary = build_level_summary(sensor_rows)
    if phase == "development":
        write_csv(result_run / "tables/development_level_summary.csv", level_summary)
    else:
        write_csv(result_run / "tables/level_summary.csv", level_summary)

    detector_results = [detector_result(sensor_rows, sweep, common) for sweep in ["geometry", "observation"]]
    prediction_results = [prediction_result(sensor_rows, sweep, "mean_inverse_axis_information", common) for sweep in ["geometry", "observation"]]
    odi_risk_results = [prediction_result(sensor_rows, sweep, "ODI_trans_median", common) for sweep in ["geometry", "observation"]]
    open_control = open_control_result(sensor_rows)

    within_results: List[Dict[str, Any]] = []
    if phase == "test":
        if lock is None:
            raise RuntimeError("REFUSE_TEST_EXECUTION: analysis lock missing during test analysis")
        for sweep in ["geometry", "observation"]:
            within_results.append(within_level_test_result(sensor_rows, sweep, lock, common))

    if phase == "development":
        development_rows = []
        for row in detector_results:
            development_rows.append({"analysis_type": "detector", **row})
        for row in prediction_results:
            development_rows.append({"analysis_type": "prediction", **row})
        for row in odi_risk_results:
            development_rows.append({"analysis_type": "odi_auxiliary_risk", **row})
        write_csv(result_run / "tables/development_correlations.csv", development_rows)
        (result_run / "reports/development_report.md").write_text(
            build_development_report(manifest, detector_results, prediction_results, open_control), encoding="utf-8"
        )
        return {"counts_match": counts_match, "gates": None, "authorizations": None}
    if phase == "quick":
        write_csv(result_run / "tables/quick_detector_results.csv", detector_results)
        write_csv(result_run / "tables/quick_prediction_results.csv", prediction_results)
        return {"counts_match": counts_match, "gates": None, "authorizations": None}

    write_csv(result_run / "tables/geometry_detector_results.csv", [detector_results[0]])
    write_csv(result_run / "tables/observation_detector_results.csv", [detector_results[1]])
    write_csv(result_run / "tables/geometry_prediction_results.csv", [prediction_results[0], odi_risk_results[0]])
    write_csv(result_run / "tables/observation_prediction_results.csv", [prediction_results[1], odi_risk_results[1]])
    write_csv(result_run / "tables/within_level_results.csv", within_results)
    mechanism = audit_mechanism(root, sensor_rows, common)
    gates = evaluate_confirmatory_gates(
        root,
        result_run,
        sensor_rows,
        process_rows,
        manifest,
        lock or {},
        detector_results,
        prediction_results,
        within_results,
        open_control,
        mechanism,
        common,
    )
    authorizations = authorization_decisions(
        gates["engineering"] == "ENGINEERING_PASS",
        gates["mechanism"] == "MECHANISM_PASS",
        gates["detector"] == "DETECTOR_PASS",
        gates["prediction"],
    )
    gate_rows = [{"gate": key, "status": value} for key, value in gates.items() if key != "checks"]
    gate_rows.extend(
        {"gate": f"check:{key}", "status": json.dumps(value, sort_keys=True, allow_nan=True)}
        for key, value in gates["checks"].items()
    )
    gate_rows.extend({"gate": key, "status": value} for key, value in authorizations.items())
    write_csv(result_run / "tables/gate_summary.csv", gate_rows)
    (result_run / "reports/stage1c_gate_report.md").write_text(
        build_gate_report(gates, authorizations, detector_results, prediction_results, odi_risk_results, within_results, open_control),
        encoding="utf-8",
    )
    (result_run / "reports/stage1c_reproducibility_report.md").write_text(
        build_reproducibility_report(manifest, lock or {}, gates), encoding="utf-8"
    )
    return {"counts_match": counts_match, "gates": gates, "authorizations": authorizations}


def detector_result(
    sensor_rows: Sequence[Mapping[str, Any]], sweep: str, common: Mapping[str, Any]
) -> Dict[str, Any]:
    levels = LEVEL_ORDERS[sweep]
    rows = with_severity(
        [row for row in sensor_rows if str(row["sweep_type"]) == sweep and str(row["level"]) in levels],
        levels,
    )
    bootstrap = block_bootstrap_spearman(
        rows,
        "severity",
        "ODI_trans_median",
        int(common["analysis"]["bootstrap_repetitions"]),
        int(common["analysis"]["bootstrap_seed"]),
    )
    trends = per_geometry_trends(rows, "severity", "ODI_trans_median")
    paired = paired_monotonicity(rows, "ODI_trans_median", levels, 1)
    severe = [row for row in rows if str(row["level"]) in levels[2:]]
    alignment = finite_array(severe, "weak_trans_subspace_alignment_median")
    return {
        "sweep_type": sweep,
        "metric_name": "ODI_trans",
        "target": "severity",
        "spearman_rho": bootstrap["rho"],
        "bootstrap_ci_low": bootstrap["bootstrap_ci_low"],
        "bootstrap_ci_high": bootstrap["bootstrap_ci_high"],
        "bootstrap_blocks": bootstrap["bootstrap_blocks"],
        "bootstrap_repetitions": bootstrap["bootstrap_repetitions"],
        "median_per_geometry_kendall_tau": trends["median_tau"],
        "positive_tau_geometry_ratio": trends["positive_ratio"],
        "per_geometry_kendall_tau": trends["serialized"],
        "paired_monotonic_rate": paired["monotonic_pair_rate"],
        "weak_alignment_severe_median": float(np.median(alignment)) if alignment.size else float("nan"),
        "weak_alignment_severe_p10": float(np.percentile(alignment, 10.0)) if alignment.size else float("nan"),
        "weak_alignment_severe_p90": float(np.percentile(alignment, 90.0)) if alignment.size else float("nan"),
        "independent_sensor_runs": len(rows),
    }


def prediction_result(
    sensor_rows: Sequence[Mapping[str, Any]],
    sweep: str,
    metric_field: str,
    common: Mapping[str, Any],
) -> Dict[str, Any]:
    levels = LEVEL_ORDERS[sweep]
    rows = with_severity(
        [row for row in sensor_rows if str(row["sweep_type"]) == sweep and str(row["level"]) in levels], levels
    )
    bootstrap = block_bootstrap_spearman(
        rows,
        metric_field,
        "mean_final_axis_error_squared",
        int(common["analysis"]["bootstrap_repetitions"]),
        int(common["analysis"]["bootstrap_seed"]),
    )
    trends = per_geometry_trends(rows, metric_field, "mean_final_axis_error_squared")
    paired = paired_monotonicity(rows, metric_field, levels, 1)
    return {
        "sweep_type": sweep,
        "metric_name": metric_field,
        "target": "mean_final_axis_error_squared",
        "spearman_rho": bootstrap["rho"],
        "bootstrap_ci_low": bootstrap["bootstrap_ci_low"],
        "bootstrap_ci_high": bootstrap["bootstrap_ci_high"],
        "bootstrap_blocks": bootstrap["bootstrap_blocks"],
        "bootstrap_repetitions": bootstrap["bootstrap_repetitions"],
        "median_per_geometry_kendall_tau": trends["median_tau"],
        "positive_tau_geometry_ratio": trends["positive_ratio"],
        "per_geometry_kendall_tau": trends["serialized"],
        "paired_monotonic_rate": paired["monotonic_pair_rate"],
        "independent_sensor_runs": len(rows),
    }


def within_level_test_result(
    sensor_rows: Sequence[Mapping[str, Any]],
    sweep: str,
    lock: Mapping[str, Any],
    common: Mapping[str, Any],
) -> Dict[str, Any]:
    medians = lock["development_level_medians"][sweep]
    rows = []
    for source in sensor_rows:
        if str(source["sweep_type"]) != sweep or str(source["level"]) not in LEVEL_ORDERS[sweep]:
            continue
        row = dict(source)
        level = str(row["level"])
        row["metric_residual"] = float(row["mean_inverse_axis_information"]) - float(
            medians[level]["mean_inverse_axis_information"]
        )
        row["target_residual"] = float(row["mean_final_axis_error_squared"]) - float(
            medians[level]["mean_final_axis_error_squared"]
        )
        rows.append(row)
    bootstrap = block_bootstrap_spearman(
        rows,
        "metric_residual",
        "target_residual",
        int(common["analysis"]["bootstrap_repetitions"]),
        int(common["analysis"]["bootstrap_seed"]),
    )
    return {
        "sweep_type": sweep,
        "metric_name": "mean_inverse_axis_information",
        "within_level_residual_spearman": bootstrap["rho"],
        "bootstrap_ci_low": bootstrap["bootstrap_ci_low"],
        "bootstrap_ci_high": bootstrap["bootstrap_ci_high"],
        "centering_source": "development_level_medians_from_analysis_lock",
        "independent_sensor_runs": len(rows),
    }


def open_control_result(sensor_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    rows = [row for row in sensor_rows if str(row["scene_family"]) == "OC"]
    trigger = finite_array(rows, "weak_axis_aligned_frame_ratio")
    return {
        "sensor_run_count": len(rows),
        "weak_axis_aligned_false_trigger_rate": float(np.mean(trigger)) if trigger.size else float("nan"),
        "weak_alignment_median": median_field(rows, "weak_trans_subspace_alignment_median"),
    }


def per_geometry_trends(
    rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str
) -> Dict[str, Any]:
    grouped: Dict[int, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["geometry_seed"])].append(row)
    values: Dict[int, float] = {}
    for seed, group in grouped.items():
        x = [float(row[x_field]) for row in group]
        y = [float(row[y_field]) for row in group]
        tau = float(kendalltau(x, y).statistic)
        values[seed] = tau
    finite = np.asarray([value for value in values.values() if np.isfinite(value)], dtype=float)
    return {
        "median_tau": float(np.median(finite)) if finite.size else float("nan"),
        "positive_ratio": float(np.mean(finite > 0.0)) if finite.size else float("nan"),
        "serialized": ";".join(f"{seed}:{values[seed]:.9g}" for seed in sorted(values)),
    }


def with_severity(rows: Sequence[Mapping[str, Any]], levels: Sequence[str]) -> List[Dict[str, Any]]:
    severity = {level: index + 1 for index, level in enumerate(levels)}
    output = []
    for source in rows:
        row = dict(source)
        row["severity"] = severity[str(row["level"])]
        output.append(row)
    return output


def audit_mechanism(
    root: Path, sensor_rows: Sequence[Mapping[str, Any]], common: Mapping[str, Any]
) -> Dict[str, Any]:
    geometry_rows = [
        row for row in sensor_rows if str(row["sweep_type"]) == "geometry" and str(row["level"]) in LEVEL_ORDERS["geometry"]
    ]
    observation_rows = [row for row in sensor_rows if str(row["sweep_type"]) == "observation"]
    geometry_groups = group_level_rows(geometry_rows)
    observation_groups = group_level_rows(observation_rows)
    geometry_structure = True
    for levels in geometry_groups.values():
        if not all(level in levels for level in LEVEL_ORDERS["geometry"]):
            geometry_structure = False
            continue
        support = [float(levels[level]["geometry_axial_support_score"]) for level in LEVEL_ORDERS["geometry"]]
        ids = [set(str(levels[level]["active_patch_ids"]).split(";")) for level in LEVEL_ORDERS["geometry"]]
        geometry_structure &= bool(support[0] > support[1] > support[2] > support[3] > 0.0)
        geometry_structure &= bool(ids[3] < ids[2] < ids[1] < ids[0])
        geometry_structure &= len({str(levels[level]["sampling_weight_checksum"]) for level in levels}) == 1
        geometry_structure &= len({str(levels[level]["non_axial_shell_checksum"]) for level in levels}) == 1
    observation_structure = True
    nested_retention = True
    for levels in observation_groups.values():
        if not all(level in levels for level in LEVEL_ORDERS["observation"]):
            observation_structure = False
            continue
        for checksum in ["planes_checksum", "gt_checksum", "candidate_uniform_checksum", "candidate_axial_checksum"]:
            observation_structure &= len({str(levels[level][checksum]) for level in levels}) == 1
        fractions = [float(levels[level]["realized_axial_point_fraction"]) for level in LEVEL_ORDERS["observation"]]
        observation_structure &= all(fractions[index] > fractions[index + 1] for index in range(3))
        masks = []
        for level in LEVEL_ORDERS["observation"]:
            observation_path = root / str(levels[level]["observations_path"])
            with np.load(observation_path) as loaded:
                masks.append(np.asarray(loaded["retained_axial_candidate_mask"], dtype=bool))
        nested_retention &= bool(
            np.all(~masks[3] | masks[2]) and np.all(~masks[2] | masks[1]) and np.all(~masks[1] | masks[0])
        )
    geometry_axis_blocks = count_axis_information_ordered_blocks(geometry_rows, LEVEL_ORDERS["geometry"])
    observation_axis_blocks = count_axis_information_ordered_blocks(observation_rows, LEVEL_ORDERS["observation"])
    return {
        "geometry_structure_pass": geometry_structure and bool(geometry_groups),
        "observation_structure_pass": observation_structure and nested_retention and bool(observation_groups),
        "observation_retention_nested": nested_retention,
        "geometry_axis_information_ordered_blocks": geometry_axis_blocks,
        "observation_axis_information_ordered_blocks": observation_axis_blocks,
        "geometry_block_count": len({int(row["geometry_seed"]) for row in geometry_rows}),
        "observation_block_count": len({int(row["geometry_seed"]) for row in observation_rows}),
    }


def group_level_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[Tuple[int, int], Dict[str, Mapping[str, Any]]]:
    grouped: Dict[Tuple[int, int], Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        grouped[(int(row["geometry_seed"]), int(row["sensor_seed"]))][str(row["level"])] = row
    return grouped


def count_axis_information_ordered_blocks(
    rows: Sequence[Mapping[str, Any]], levels: Sequence[str]
) -> int:
    by_geometry: Dict[int, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_geometry[int(row["geometry_seed"])][str(row["level"])].append(
            float(row["axis_information_normalized_median"])
        )
    passed = 0
    for level_values in by_geometry.values():
        if not all(level in level_values for level in levels):
            continue
        medians = [float(np.median(level_values[level])) for level in levels]
        if all(medians[index] > medians[index + 1] for index in range(3)):
            passed += 1
    return passed


def evaluate_confirmatory_gates(
    root: Path,
    result_run: Path,
    sensor_rows: Sequence[Mapping[str, Any]],
    process_rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    lock: Mapping[str, Any],
    detector_results: Sequence[Mapping[str, Any]],
    prediction_results: Sequence[Mapping[str, Any]],
    within_results: Sequence[Mapping[str, Any]],
    open_control: Mapping[str, Any],
    mechanism: Mapping[str, Any],
    common: Mapping[str, Any],
) -> Dict[str, Any]:
    provenance_paths = [
        root / "results/metric_redesign_stage1c/test_provenance_run1.json",
        root / "results/metric_redesign_stage1c/test_provenance_run2.json",
    ]
    provenance_records = [read_json(path) for path in provenance_paths]
    provenance = validate_test_provenance(provenance_records, git_commit(root), str(lock["source_tree_sha256"]))
    noise = build_process_noise_audit(process_rows, 1440)
    per_sensor_trials: Dict[Tuple[str, int], int] = defaultdict(int)
    for row in process_rows:
        per_sensor_trials[(str(row["sequence_id"]), int(row["sensor_seed"]))] += 1
    trajectories_complete = all((root / str(row["trajectory_path"])).exists() for row in process_rows)
    low_unique = max(
        int(lock.get("development_low_information_ratio_unique_count", 0)),
        unique_finite_count(sensor_rows, "low_axis_information_ratio"),
    )
    duration_unique = max(
        int(lock.get("development_longest_low_information_duration_unique_count", 0)),
        unique_finite_count(sensor_rows, "longest_low_information_duration_s"),
    )
    engineering_checks = {
        "verified_pytest_twice": provenance["all_valid"],
        "test_provenance_current_commit": all(record["git_commit"] == git_commit(root) for record in provenance_records),
        "source_tree_matches_lock": manifest["test_provenance"]["source_hash_matched"],
        "config_matches_lock": manifest["test_provenance"]["config_hash_matched"],
        "git_status_clean": git_status_clean(root),
        "development_test_isolated": "/development/" not in str(result_run) and "/test/" in str(result_run),
        "combined_sensor_runs": int(lock["development_sensor_run_count"]) + len(sensor_rows),
        "combined_process_trials": int(lock["development_process_trial_count"]) + len(process_rows),
        "thirty_trials_per_sensor": bool(per_sensor_trials) and all(value == 30 for value in per_sensor_trials.values()),
        "trajectories_complete": trajectories_complete,
        "no_gt_leakage_regression": provenance["all_valid"],
        "process_noise_pairing_violations": noise["pairing_violations"],
        "process_noise_independence_violations": noise["independence_violations"],
        "test_unique_noise_sequences": noise["actual_unique_noise_sequences"],
        "manifest_version_tracking": all(
            key in manifest
            for key in [
                "data_generation_git_commit",
                "analysis_git_commit",
                "test_execution_git_commit",
                "data_generation_source_tree_sha256",
                "analysis_source_tree_sha256",
                "test_source_tree_sha256",
                "analysis_lock_sha256",
                "config_bundle_sha256",
            ]
        ),
        "low_information_ratio_unique_count": low_unique,
        "longest_low_information_duration_unique_count": duration_unique,
    }
    engineering_pass = bool(
        engineering_checks["verified_pytest_twice"]
        and engineering_checks["test_provenance_current_commit"]
        and engineering_checks["source_tree_matches_lock"]
        and engineering_checks["config_matches_lock"]
        and engineering_checks["git_status_clean"]
        and engineering_checks["development_test_isolated"]
        and engineering_checks["combined_sensor_runs"] == 234
        and engineering_checks["combined_process_trials"] == 7020
        and engineering_checks["thirty_trials_per_sensor"]
        and engineering_checks["trajectories_complete"]
        and engineering_checks["process_noise_pairing_violations"] == 0
        and engineering_checks["process_noise_independence_violations"] == 0
        and engineering_checks["test_unique_noise_sequences"] == 1440
        and engineering_checks["manifest_version_tracking"]
        and low_unique > 1
        and duration_unique > 1
    )
    mechanism_pass = bool(
        mechanism["geometry_structure_pass"]
        and mechanism["observation_structure_pass"]
        and int(mechanism["geometry_axis_information_ordered_blocks"])
        >= int(common["gates"]["mechanism_geometry_blocks_required"])
        and int(mechanism["observation_axis_information_ordered_blocks"])
        >= int(common["gates"]["mechanism_observation_blocks_required"])
    )
    detector_checks = {row["sweep_type"]: detector_gate_pass(row, common) for row in detector_results}
    detector_pass = all(detector_checks.values()) and bool(
        float(open_control["weak_axis_aligned_false_trigger_rate"])
        <= float(common["gates"]["open_control_false_trigger_max"])
    )
    prediction_checks = {}
    for result in prediction_results:
        sweep = str(result["sweep_type"])
        within = next(row for row in within_results if str(row["sweep_type"]) == sweep)
        prediction_checks[sweep] = prediction_gate_pass(result, within, common)
    passed_prediction_sweeps = sum(prediction_checks.values())
    prediction_status = "PREDICTION_PASS" if passed_prediction_sweeps == 2 else (
        "PREDICTION_PARTIAL" if passed_prediction_sweeps == 1 else "PREDICTION_FAIL"
    )
    return {
        "engineering": "ENGINEERING_PASS" if engineering_pass else "ENGINEERING_FAIL",
        "mechanism": "MECHANISM_PASS" if mechanism_pass else "MECHANISM_FAIL",
        "detector": "DETECTOR_PASS" if detector_pass else "DETECTOR_FAIL",
        "prediction": prediction_status,
        "checks": {
            "engineering": engineering_checks,
            "mechanism": dict(mechanism),
            "detector": {**detector_checks, "open_control": dict(open_control)},
            "prediction": prediction_checks,
        },
    }


def detector_gate_pass(result: Mapping[str, Any], common: Mapping[str, Any]) -> bool:
    gates = common["gates"]
    return bool(
        float(result["spearman_rho"]) >= float(gates["detector_severity_rho_min"])
        and float(result["bootstrap_ci_low"]) > 0.0
        and float(result["median_per_geometry_kendall_tau"]) >= float(gates["detector_kendall_median_min"])
        and float(result["positive_tau_geometry_ratio"]) >= float(gates["detector_positive_geometry_ratio_min"])
        and float(result["paired_monotonic_rate"]) >= float(gates["detector_paired_monotonic_rate_min"])
        and float(result["weak_alignment_severe_median"]) >= float(gates["weak_alignment_median_min"])
    )


def prediction_gate_pass(
    result: Mapping[str, Any], within: Mapping[str, Any], common: Mapping[str, Any]
) -> bool:
    gates = common["gates"]
    residual_rho = float(within["within_level_residual_spearman"])
    residual_negative_ci = float(within["bootstrap_ci_low"]) + float(within["bootstrap_ci_high"]) < 0.0
    obvious_reversal = residual_rho < float(gates["residual_obvious_reversal_rho"]) and residual_negative_ci
    return bool(
        float(result["spearman_rho"]) >= float(gates["prediction_rho_min"])
        and float(result["bootstrap_ci_low"]) > 0.0
        and float(result["positive_tau_geometry_ratio"]) >= float(gates["prediction_positive_geometry_ratio_min"])
        and float(result["paired_monotonic_rate"]) >= float(gates["prediction_paired_monotonic_rate_min"])
        and not obvious_reversal
    )


def authorization_decisions(
    engineering_pass: bool,
    mechanism_pass: bool,
    detector_pass: bool,
    prediction_status: str,
) -> Dict[str, bool]:
    return {
        "WEAK_UPDATE_AUTHORIZED": bool(engineering_pass and mechanism_pass and detector_pass),
        "RISK_WARNING_AUTHORIZED": bool(
            engineering_pass and mechanism_pass and prediction_status == "PREDICTION_PASS"
        ),
    }


def lock_stage1c_analysis(root: Path, development_run_dir: Path) -> Dict[str, Any]:
    root = Path(root).resolve()
    run_dir = Path(development_run_dir).resolve()
    expected_parent = (root / "results/metric_redesign_stage1c/development").resolve()
    if expected_parent not in run_dir.parents:
        raise ValueError("--lock-analysis may read only a Stage 1c development run")
    manifest_path = run_dir / "manifests/development_manifest.json"
    calibration_path = run_dir / "threshold_calibration.json"
    if not manifest_path.exists() or not calibration_path.exists():
        raise FileNotFoundError("Development manifest and threshold calibration are required before locking")
    output_path = run_dir / "analysis_lock.json"
    if output_path.exists():
        raise FileExistsError("analysis_lock.json already exists; old locks are immutable")
    manifest = read_json(manifest_path)
    if int(manifest["sensor_run_count"]) != 90 or int(manifest["process_trial_count"]) != 2700:
        raise ValueError("Development run is incomplete and cannot be locked")
    calibration = read_json(calibration_path)
    sensor_rows = read_csv(run_dir / "tables/sensor_run_summary.csv")
    medians = development_level_medians(sensor_rows)
    common = load_yaml(root / "configs/redesign/stage1c_common.yaml")
    development = normalize_phase_config(load_yaml(root / "configs/redesign/stage1c_development.yaml"))
    reserved = normalize_phase_config(load_yaml(root / "configs/redesign/stage1c_test.yaml"))
    lock = build_analysis_lock(
        root,
        run_dir,
        calibration,
        manifest,
        medians,
        common,
        development,
        reserved,
    )
    write_json(output_path, lock)
    return lock


def analyze_existing_stage1c(root: Path, run_dir: Path) -> Dict[str, Any]:
    root = Path(root).resolve()
    result_run = Path(run_dir).resolve()
    manifests = sorted((result_run / "manifests").glob("*_manifest.json"))
    if len(manifests) != 1:
        raise FileNotFoundError("analyze-only requires exactly one Stage 1c phase manifest")
    manifest = read_json(manifests[0])
    phase = str(manifest["phase"])
    sensor_rows = read_csv(result_run / "tables/sensor_run_summary.csv")
    process_rows = read_csv(result_run / "tables/process_trial_summary.csv")
    common = load_yaml(root / "configs/redesign/stage1c_common.yaml")
    lock = None
    if phase == "test":
        lock_path = root / str(manifest["analysis_lock_path"])
        lock = read_json(lock_path)
        verify_analysis_lock(root, lock, require_clean=True)
        if sha256_file(lock_path) != str(manifest["analysis_lock_sha256"]):
            raise RuntimeError("REFUSE_TEST_EXECUTION: analysis lock artifact hash changed")
        provenance_paths = [
            root / "results/metric_redesign_stage1c/test_provenance_run1.json",
            root / "results/metric_redesign_stage1c/test_provenance_run2.json",
        ]
        if not all(path.exists() for path in provenance_paths):
            raise RuntimeError("REFUSE_TEST_EXECUTION: verified pytest provenance is missing")
        provenance = validate_test_provenance(
            [read_json(path) for path in provenance_paths],
            git_commit(root),
            str(lock["source_tree_sha256"]),
        )
        if not provenance["all_valid"]:
            raise RuntimeError("REFUSE_TEST_EXECUTION: analyze-only provenance no longer matches")
    analysis = analyze_stage1c_run(root, result_run, sensor_rows, process_rows, common, phase, manifest, lock)
    manifest["analysis_git_commit"] = git_commit(root)
    manifest["analysis_source_tree_sha256"] = compute_source_tree_hash(stage1c_source_paths(root))
    manifest["gates"] = analysis.get("gates")
    manifest["authorizations"] = analysis.get("authorizations")
    append_analysis_history(manifest, root)
    write_json(manifests[0], manifest)
    return manifest


def append_analysis_history(manifest: Dict[str, Any], root: Path) -> None:
    manifest.setdefault("analysis_history", []).append(
        {
            "analysis_timestamp": utc_now(),
            "analysis_git_commit": git_commit(root),
            "analysis_source_tree_sha256": compute_source_tree_hash(stage1c_source_paths(root)),
        }
    )


def development_level_medians(sensor_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for sweep, levels in LEVEL_ORDERS.items():
        output[sweep] = {}
        for level in levels:
            rows = [
                row for row in sensor_rows if str(row["sweep_type"]) == sweep and str(row["level"]) == level
            ]
            output[sweep][level] = {
                "mean_inverse_axis_information": median_field(rows, "mean_inverse_axis_information"),
                "mean_final_axis_error_squared": median_field(rows, "mean_final_axis_error_squared"),
            }
    return output


def build_level_summary(sensor_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for row in sensor_rows:
        grouped[(str(row["sweep_type"]), str(row["level"]))].append(row)
    output = []
    for (sweep, level), rows in sorted(grouped.items()):
        output.append(
            {
                "sweep_type": sweep,
                "level": level,
                "independent_sensor_runs": len(rows),
                "geometry_axial_support_score": median_field(rows, "geometry_axial_support_score"),
                "realized_axial_point_fraction": median_field(rows, "realized_axial_point_fraction"),
                "ODI_trans_median": median_field(rows, "ODI_trans_median"),
                "axis_information_normalized_median": median_field(rows, "axis_information_normalized_median"),
                "weak_trans_subspace_alignment_median": median_field(rows, "weak_trans_subspace_alignment_median"),
                "mean_inverse_axis_information": median_field(rows, "mean_inverse_axis_information"),
                "low_axis_information_ratio": median_field(rows, "low_axis_information_ratio"),
                "longest_low_information_duration_s": median_field(rows, "longest_low_information_duration_s"),
                "mean_final_axis_error_squared": median_field(rows, "mean_final_axis_error_squared"),
            }
        )
    return output


def build_development_report(
    manifest: Mapping[str, Any],
    detector: Sequence[Mapping[str, Any]],
    prediction: Sequence[Mapping[str, Any]],
    open_control: Mapping[str, Any],
) -> str:
    lines = [
        "# Stage 1c Development Report",
        "",
        "Development results are calibration and engineering evidence only. Reserved test seeds were not run.",
        "",
        f"- Independent sensor runs: {manifest['sensor_run_count']}",
        f"- Process trials: {manifest['process_trial_count']}",
        f"- Unique process-noise sequences: {manifest['unique_process_noise_sequences']}",
        f"- Open-control weak-axis false-trigger rate: {format_float(open_control['weak_axis_aligned_false_trigger_rate'])}",
        "",
        "## Detector development diagnostics",
        "",
    ]
    for row in detector:
        lines.append(
            f"- {row['sweep_type']}: severity rho={format_float(row['spearman_rho'])}, "
            f"CI=[{format_float(row['bootstrap_ci_low'])}, {format_float(row['bootstrap_ci_high'])}]"
        )
    lines.extend(["", "## Exposure development diagnostics", ""])
    for row in prediction:
        lines.append(
            f"- {row['sweep_type']}: exposure-error rho={format_float(row['spearman_rho'])}, "
            f"CI=[{format_float(row['bootstrap_ci_low'])}, {format_float(row['bootstrap_ci_high'])}]"
        )
    lines.extend(["", "No Stage 1c authorization is issued from development data.", ""])
    return "\n".join(lines)


def build_gate_report(
    gates: Mapping[str, Any],
    authorizations: Mapping[str, bool],
    detector: Sequence[Mapping[str, Any]],
    prediction: Sequence[Mapping[str, Any]],
    odi_risk: Sequence[Mapping[str, Any]],
    within: Sequence[Mapping[str, Any]],
    open_control: Mapping[str, Any],
) -> str:
    lines = [
        "# Metric Redesign Stage 1c Confirmatory Gate Report",
        "",
        f"- Engineering: **{gates['engineering']}**",
        f"- Mechanism: **{gates['mechanism']}**",
        f"- Detector: **{gates['detector']}**",
        f"- Prediction: **{gates['prediction']}**",
        f"- WEAK_UPDATE_AUTHORIZED: **{str(authorizations['WEAK_UPDATE_AUTHORIZED']).lower()}**",
        f"- RISK_WARNING_AUTHORIZED: **{str(authorizations['RISK_WARNING_AUTHORIZED']).lower()}**",
        "",
        "## Detector results",
        "",
    ]
    for row in detector:
        lines.append(
            f"- {row['sweep_type']}: rho={format_float(row['spearman_rho'])}, "
            f"CI=[{format_float(row['bootstrap_ci_low'])}, {format_float(row['bootstrap_ci_high'])}], "
            f"median tau={format_float(row['median_per_geometry_kendall_tau'])}, "
            f"positive geometry ratio={format_float(row['positive_tau_geometry_ratio'])}, "
            f"paired rate={format_float(row['paired_monotonic_rate'])}, "
            f"severe weak alignment={format_float(row['weak_alignment_severe_median'])}."
        )
    lines.extend(
        [
            "",
            f"Open-control weak-axis aligned false-trigger rate: {format_float(open_control['weak_axis_aligned_false_trigger_rate'])}.",
            "",
            "## Primary exposure prediction",
            "",
        ]
    )
    for row in prediction:
        lines.append(
            f"- {row['sweep_type']}: rho={format_float(row['spearman_rho'])}, "
            f"CI=[{format_float(row['bootstrap_ci_low'])}, {format_float(row['bootstrap_ci_high'])}], "
            f"positive geometry ratio={format_float(row['positive_tau_geometry_ratio'])}, "
            f"paired rate={format_float(row['paired_monotonic_rate'])}."
        )
    lines.extend(["", "## ODI auxiliary risk association", ""])
    for row in odi_risk:
        lines.append(
            f"- {row['sweep_type']}: rho={format_float(row['spearman_rho'])}, "
            f"CI=[{format_float(row['bootstrap_ci_low'])}, {format_float(row['bootstrap_ci_high'])}]."
        )
    lines.extend(["", "## Development-centered test residuals", ""])
    for row in within:
        lines.append(
            f"- {row['sweep_type']}: rho={format_float(row['within_level_residual_spearman'])}, "
            f"CI=[{format_float(row['bootstrap_ci_low'])}, {format_float(row['bootstrap_ci_high'])}]."
        )
    lines.extend(["", "## Audited checks", ""])
    for category, checks in gates["checks"].items():
        lines.append(f"- {category}: `{json.dumps(checks, sort_keys=True, allow_nan=True)}`")
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "Stage 1c authorizes or rejects only the next controlled research stage. It does not implement a weak-subspace update, integrate FAST-LIO2, validate online drift warning in a real LIO system, or complete Degen-LIO.",
            "",
        ]
    )
    return "\n".join(lines)


def build_reproducibility_report(
    manifest: Mapping[str, Any], lock: Mapping[str, Any], gates: Mapping[str, Any]
) -> str:
    provenance = manifest["test_provenance"]
    return "\n".join(
        [
            "# Stage 1c Reproducibility Report",
            "",
            f"- Analysis lock commit: `{provenance.get('analysis_lock_commit')}`",
            f"- Analysis source commit at lock creation: `{lock.get('git_commit_at_lock')}`",
            f"- Test execution commit: `{manifest.get('test_execution_git_commit')}`",
            f"- Data generation commit: `{manifest.get('data_generation_git_commit')}`",
            f"- Analysis commit: `{manifest.get('analysis_git_commit')}`",
            f"- Source hash matched: `{provenance.get('source_hash_matched')}`",
            f"- Config hash matched: `{provenance.get('config_hash_matched')}`",
            f"- Analysis lock SHA-256: `{manifest.get('analysis_lock_sha256')}`",
            f"- Engineering Gate: `{gates.get('engineering')}`",
            "",
            "The test run used the frozen development threshold and did not recompute or tune it from reserved test data.",
            "",
        ]
    )


def finite_array(rows: Sequence[Mapping[str, Any]], field: str) -> np.ndarray:
    values = np.asarray([float(row[field]) for row in rows], dtype=float)
    return values[np.isfinite(values)]


def median_field(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = finite_array(rows, field)
    return float(np.median(values)) if values.size else float("nan")


def unique_finite_count(rows: Sequence[Mapping[str, Any]], field: str) -> int:
    values = finite_array(rows, field)
    return len(set(np.round(values, 12).tolist()))


def array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(value))
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(str(array.shape).encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()


def format_float(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return "nan" if not np.isfinite(number) else f"{number:.6g}"
