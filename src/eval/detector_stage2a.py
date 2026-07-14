"""Detector-only Stage 2A development and independent confirmation pipeline."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np
from scipy.stats import kendalltau

from degen_detector.odi_tracker import compute_metrics_for_sequence
from degen_detector.weak_direction import compute_subspace_axis_alignment
from eval.analysis_lock import (
    compute_bundle_hash,
    compute_directory_hash,
    compute_source_tree_hash,
    git_commit,
    git_path_commit,
    git_status_clean,
    sha256_file,
)
from eval.detector_stage2a_lock import (
    build_detector_lock,
    calibrate_odi_trigger_threshold,
    detector_config_paths,
    detector_source_paths,
    verify_detector_lock,
)
from eval.hierarchical_statistics import block_bootstrap_spearman, paired_monotonicity
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
    write_structured_csv,
)
from minibench.nested_geometry_observations import (
    array_checksum,
    audit_nested_geometry_levels,
    simulate_nested_geometry_observations,
)
from minibench.observation_simulator import save_observations


LEVELS = {"geometry": ["L1", "L2", "L3", "L4"], "observation": ["O1", "O2", "O3", "O4"]}


def run_detector_stage2a(
    root: Path,
    phase: str,
    run_id: str,
    common_config_path: Path,
    phase_config_path: Path,
    detector_config_path: Path,
    workers: int = 1,
    resume: bool = False,
    overwrite: bool = False,
    detector_lock_path: Path | None = None,
) -> Dict[str, Any]:
    del workers  # The detector-only workload is deterministic and vectorized per sensor run.
    if phase not in {"quick", "development", "test"}:
        raise ValueError(f"unsupported Stage 2A phase: {phase}")
    if not run_id:
        raise ValueError("run_id is required")
    root = Path(root).resolve()
    common = load_yaml(common_config_path)
    phase_config = normalize_phase_config(load_yaml(phase_config_path))
    detector = load_yaml(detector_config_path)
    validate_seed_contract(root, phase, phase_config)

    lock = None
    lock_verification = None
    pytest_provenance = None
    if phase == "test":
        if detector_lock_path is None or not Path(detector_lock_path).exists():
            raise RuntimeError("REFUSE_TEST_EXECUTION: detector lock is required")
        lock = read_json(Path(detector_lock_path))
        lock_verification = verify_detector_lock(root, lock, require_clean=True)
        validate_reserved_seeds(phase_config, lock)
        git_path_commit(root, Path(detector_lock_path))
        provenance_path = root / "results/detector_stage2a/pytest_provenance.json"
        if not provenance_path.exists():
            raise RuntimeError("REFUSE_TEST_EXECUTION: current-commit full pytest provenance is required")
        pytest_provenance = read_json(provenance_path)
        if not (
            int(pytest_provenance.get("return_code", -1)) == 0
            and pytest_provenance.get("status") == "passed"
            and pytest_provenance.get("git_commit") == git_commit(root)
            and bool(pytest_provenance.get("git_status_clean"))
        ):
            raise RuntimeError("REFUSE_TEST_EXECUTION: full pytest provenance does not match test commit")

    started = time.time()
    data_run = root / "data/detector_stage2a" / phase / run_id
    result_run = root / "results/detector_stage2a" / phase / run_id
    prepare_run_directories(data_run, result_run, resume, overwrite)
    for name in ["tables", "reports", "manifests", "frames"]:
        (result_run / name).mkdir(parents=True, exist_ok=True)

    source_hash = compute_source_tree_hash(detector_source_paths(root))
    config_hash = compute_bundle_hash(detector_config_paths(root))
    records: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []
    for geometry_seed in phase_config["geometry_seeds"]:
        specs = build_specs(common, int(geometry_seed), phase)
        sequence_dirs: Dict[str, Path] = {}
        for spec in specs:
            sequence_dir = data_run / str(spec["sequence_id"])
            generate_or_validate_sequence(sequence_dir, spec)
            sequence_dirs[str(spec["sequence_id"])] = sequence_dir
        for sensor_seed in phase_config["sensor_seeds"]:
            local_records = []
            for spec in specs:
                sequence_dir = sequence_dirs[str(spec["sequence_id"])]
                sensor_dir = sequence_dir / f"sensor_{int(sensor_seed):03d}"
                observation_path = sensor_dir / "observations.npz"
                if resume and observation_path.exists():
                    observations = load_npz(observation_path)
                elif spec["sweep_type"] == "geometry" and spec["level"] in LEVELS["geometry"]:
                    sensor_dir.mkdir(parents=True, exist_ok=True)
                    observations = simulate_nested_geometry_observations(
                        sequence_dir,
                        detector_config_path,
                        int(geometry_seed),
                        int(sensor_seed),
                        float(common["geometry_points_per_square_meter"]),
                        int(common["geometry_min_points_per_patch"]),
                    )
                    save_observations(observations, observation_path)
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
                record = build_sensor_record(
                    root,
                    spec,
                    int(sensor_seed),
                    observation_path,
                    observations,
                    metrics,
                )
                record["_metrics"] = metrics
                local_records.append(record)
                records.append(record)

            geometry_records = {
                str(record["level"]): record
                for record in local_records
                if record["sweep_type"] == "geometry" and record["level"] in LEVELS["geometry"]
            }
            geometry_observations = {
                level: load_npz(root / str(record["observations_path"]))
                for level, record in geometry_records.items()
            }
            audit = audit_nested_geometry_levels(geometry_observations)
            for row in audit["pair_rows"]:
                audit_rows.append(
                    {"geometry_seed": geometry_seed, "sensor_seed": sensor_seed, **row}
                )
            for level, record in geometry_records.items():
                record.update(
                    {
                        "parent_level": {"L1": "", "L2": "L1", "L3": "L2", "L4": "L3"}[level],
                        "parent_measurement_subset_valid": audit["measurement_sets_strictly_nested"],
                        "shared_measurements_identical": audit["shared_measurements_identical"],
                        "delta_H_min_eigenvalue": audit["delta_H_min_eigenvalue"],
                        "psd_increment_valid": audit["psd_increment_valid"],
                    }
                )

    threshold = resolve_odi_threshold(records, common, phase, lock, result_run)
    sensor_rows = []
    for record in records:
        metrics = record.pop("_metrics")
        apply_trigger_threshold(metrics, float(threshold["odi_trigger_threshold"]))
        metrics_path = result_run / "frames" / str(record["sequence_id"]) / f"sensor_{record['sensor_seed']:03d}.csv"
        write_structured_csv(metrics, metrics_path)
        record["metrics_path"] = relative(root, metrics_path)
        record.update(summarize_frame_metrics(metrics))
        sensor_rows.append(record)

    write_csv(result_run / "tables/sensor_run_summary.csv", sensor_rows)
    write_csv(result_run / "tables/geometry_nested_audit.csv", audit_rows)
    write_csv(result_run / "tables/level_summary.csv", build_level_summary(sensor_rows))
    detector_results = [detector_result(sensor_rows, sweep, common) for sweep in ["geometry", "observation"]]
    direction_results = [direction_result(sensor_rows, sweep) for sweep in ["geometry", "observation"]]
    open_control = open_control_result(sensor_rows)
    mechanism = mechanism_result(root, sensor_rows, audit_rows)
    write_csv(result_run / "tables/detector_results.csv", detector_results)
    write_csv(result_run / "tables/direction_results.csv", direction_results)
    write_csv(result_run / "tables/mechanism_summary.csv", [mechanism])

    manifest: Dict[str, Any] = {
        "stage": "detector_consolidation_stage2a",
        "phase": phase,
        "run_id": run_id,
        "status": "OK" if len(sensor_rows) == int(phase_config["expected_sensor_runs"]) else "INCOMPLETE",
        "sensor_run_count": len(sensor_rows),
        "expected_sensor_runs": int(phase_config["expected_sensor_runs"]),
        "process_trial_count": 0,
        "data_run_dir": relative(root, data_run),
        "result_run_dir": relative(root, result_run),
        "data_generation_git_commit": git_commit(root),
        "analysis_git_commit": git_commit(root),
        "source_tree_sha256": source_hash,
        "config_bundle_sha256": config_hash,
        "detector_lock_path": relative(root, Path(detector_lock_path)) if detector_lock_path else None,
        "detector_lock_sha256": sha256_file(Path(detector_lock_path)) if detector_lock_path else None,
        "odi_trigger_threshold": float(threshold["odi_trigger_threshold"]),
        "git_status_clean_at_start": bool(lock_verification["git_status_clean"]) if lock_verification else git_status_clean(root),
        "pytest_provenance": pytest_provenance,
        "analysis_history": [analysis_record(root)],
    }
    gates = None
    authorizations = None
    if phase == "test":
        gates = evaluate_gates(
            root,
            manifest,
            detector_results,
            direction_results,
            open_control,
            mechanism,
            common,
            lock_verification or {},
        )
        authorizations = authorization_decisions(gates)
        write_gate_outputs(result_run, gates, authorizations, detector_results, direction_results, open_control)
        manifest["gates"] = gates
        manifest["authorizations"] = authorizations
    elif phase == "development":
        (result_run / "reports/development_report.md").write_text(
            build_development_report(manifest, detector_results, direction_results, open_control, mechanism),
            encoding="utf-8",
        )
    write_json(result_run / f"manifests/{phase}_manifest.json", manifest)
    if phase == "test":
        export_current_artifacts(root, result_run, Path(detector_lock_path), manifest)
    manifest["runtime_seconds"] = round(time.time() - started, 6)
    write_json(result_run / f"manifests/{phase}_manifest.json", manifest)
    if phase == "test":
        write_json(root / "artifacts/current/detector_stage2a/test_manifest.json", manifest)
    return manifest


def normalize_phase_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    output = dict(config)
    output["geometry_seeds"] = [int(value) for value in config["geometry_seeds"]]
    output["sensor_seeds"] = [int(value) for value in config["sensor_seeds"]]
    return output


def validate_seed_contract(root: Path, phase: str, phase_config: Mapping[str, Any]) -> None:
    development = normalize_phase_config(load_yaml(root / "configs/redesign/detector_stage2a_development.yaml"))
    reserved = normalize_phase_config(load_yaml(root / "configs/redesign/detector_stage2a_test.yaml"))
    for field in ["geometry_seeds", "sensor_seeds"]:
        if set(development[field]) & set(reserved[field]):
            raise RuntimeError("REFUSE_TEST_EXECUTION: development/test seed overlap")
    if phase == "test":
        for field in ["geometry_seeds", "sensor_seeds"]:
            if list(phase_config[field]) != list(reserved[field]):
                raise RuntimeError(f"REFUSE_TEST_EXECUTION: reserved {field} changed")


def validate_reserved_seeds(config: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    if list(config["geometry_seeds"]) != list(lock["reserved_test_geometry_seeds"]):
        raise RuntimeError("REFUSE_TEST_EXECUTION: geometry seeds do not match detector lock")
    if list(config["sensor_seeds"]) != list(lock["reserved_test_sensor_seeds"]):
        raise RuntimeError("REFUSE_TEST_EXECUTION: sensor seeds do not match detector lock")


def prepare_run_directories(data_run: Path, result_run: Path, resume: bool, overwrite: bool) -> None:
    existing = [path for path in [data_run, result_run] if path.exists()]
    if existing and overwrite:
        for path in existing:
            shutil.rmtree(path)
    elif existing and not resume:
        raise FileExistsError("Stage 2A run exists; use --resume or --overwrite")
    data_run.mkdir(parents=True, exist_ok=True)
    result_run.mkdir(parents=True, exist_ok=True)


def build_specs(common: Mapping[str, Any], geometry_seed: int, phase: str) -> List[Dict[str, Any]]:
    scene = common["scene"]
    specs = [make_spec(scene, "geometry", "OC", geometry_seed, phase, scene_family="OC")]
    specs[0]["sequence_id"] = f"stage2a_{phase}_open_control_G{geometry_seed}"
    for level, count in common["geometry_levels"].items():
        spec = make_spec(scene, "geometry", str(level), geometry_seed, phase, active_patch_count=int(count))
        spec["sequence_id"] = f"stage2a_{phase}_geometry_{level}_G{geometry_seed}"
        specs.append(spec)
    for level, probability in common["observation_levels"].items():
        spec = make_spec(
            scene,
            "observation",
            str(level),
            geometry_seed,
            phase,
            active_patch_count=int(scene["master_axial_patch_pool_size"]),
            keep_probability=float(probability),
        )
        spec["sequence_id"] = f"stage2a_{phase}_observation_{level}_G{geometry_seed}"
        specs.append(spec)
    return specs


def build_sensor_record(
    root: Path,
    spec: Mapping[str, Any],
    sensor_seed: int,
    observation_path: Path,
    observations: Mapping[str, np.ndarray],
    metrics: np.ndarray,
) -> Dict[str, Any]:
    axial = np.asarray(observations.get("is_axial_support", np.zeros(metrics.shape[0], dtype=bool)))
    record: Dict[str, Any] = {
        "phase": spec["split"],
        "sweep_type": spec["sweep_type"],
        "sequence_id": spec["sequence_id"],
        "level": spec["level"],
        "scene_family": spec["scene_family"],
        "geometry_seed": int(spec["geometry_seed"]),
        "sensor_seed": int(sensor_seed),
        "observations_path": relative(root, observation_path),
        "realized_total_points": int(axial.size),
        "realized_axial_points": int(np.sum(axial)),
        "realized_axial_point_fraction": float(np.mean(axial)),
        "measurement_set_checksum": scalar_string(observations.get("measurement_set_checksum"), "not_applicable"),
        "shell_measurement_checksum": scalar_string(observations.get("shell_measurement_checksum"), "not_applicable"),
        "axial_measurement_checksum": scalar_string(observations.get("axial_measurement_checksum"), "not_applicable"),
        "candidate_uniform_checksum": array_checksum(observations["candidate_uniforms"])
        if "candidate_uniforms" in observations
        else "not_applicable",
        "candidate_axial_checksum": array_checksum(observations["candidate_is_axial"])
        if "candidate_is_axial" in observations
        else "not_applicable",
        "retained_axial_checksum": array_checksum(observations["retained_axial_candidate_mask"])
        if "retained_axial_candidate_mask" in observations
        else "not_applicable",
    }
    return record


def resolve_odi_threshold(
    records: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any],
    phase: str,
    lock: Mapping[str, Any] | None,
    result_run: Path,
) -> Dict[str, Any]:
    if phase == "test":
        if lock is None or "odi_trigger_threshold" not in lock:
            raise RuntimeError("REFUSE_TEST_EXECUTION: locked ODI threshold missing")
        return {
            "trigger_control_quantile": float(lock["trigger_control_quantile"]),
            "odi_trigger_threshold": float(lock["odi_trigger_threshold"]),
            "calibration_source": "development_open_control_only",
        }
    values = np.concatenate(
        [np.asarray(record["_metrics"]["ODI_trans"], dtype=float) for record in records if record["level"] == "OC"]
    )
    quantile = float(common["analysis"]["odi_trigger_control_quantile"])
    threshold = {
        "trigger_control_quantile": quantile,
        "odi_trigger_threshold": calibrate_odi_trigger_threshold(values, quantile),
        "calibration_source": "development_open_control_only",
        "calibration_frame_count": int(values.size),
        "calibration_data_sha256": array_checksum(values),
    }
    write_json(result_run / "odi_threshold_calibration.json", threshold)
    write_csv(result_run / "tables/odi_threshold_calibration.csv", [threshold])
    return threshold


def apply_trigger_threshold(metrics: np.ndarray, threshold: float) -> None:
    triggered = np.asarray(metrics["ODI_trans"] >= float(threshold), dtype=np.int32)
    metrics["degeneracy_triggered"] = triggered
    metrics["actionable_direction"] = triggered * np.asarray(metrics["primary_direction_stable"], dtype=np.int32)


def summarize_frame_metrics(metrics: np.ndarray) -> Dict[str, Any]:
    alignment = finite(metrics["primary_direction_axis_alignment"])
    return {
        "frame_count": int(metrics.shape[0]),
        "ODI_trans_median": float(np.median(metrics["ODI_trans"])),
        "axis_information_raw_median": float(np.median(metrics["axis_information_raw"])),
        "axis_information_normalized_median": float(np.median(metrics["axis_information_normalized"])),
        "primary_direction_axis_alignment_median": float(np.median(alignment)) if alignment.size else float("nan"),
        "primary_direction_axis_alignment_p10": float(np.percentile(alignment, 10.0)) if alignment.size else float("nan"),
        "primary_direction_stable_rate": float(np.mean(metrics["primary_direction_stable"])),
        "degeneracy_trigger_rate": float(np.mean(metrics["degeneracy_triggered"])),
        "actionable_direction_rate": float(np.mean(metrics["actionable_direction"])),
        "weak_subspace_trigger_rate": float(np.mean(metrics["weak_subspace_triggered"])),
    }


def detector_result(rows: Sequence[Mapping[str, Any]], sweep: str, common: Mapping[str, Any]) -> Dict[str, Any]:
    levels = LEVELS[sweep]
    selected = severity_rows(rows, sweep, levels)
    bootstrap = block_bootstrap_spearman(
        selected,
        "severity",
        "ODI_trans_median",
        int(common["analysis"]["bootstrap_repetitions"]),
        int(common["analysis"]["bootstrap_seed"]),
    )
    trends = per_geometry_trends(selected, "severity", "ODI_trans_median")
    paired = paired_monotonicity(selected, "ODI_trans_median", levels, 1)
    return {
        "sweep_type": sweep,
        "spearman_rho": bootstrap["rho"],
        "bootstrap_ci_low": bootstrap["bootstrap_ci_low"],
        "bootstrap_ci_high": bootstrap["bootstrap_ci_high"],
        "bootstrap_blocks": bootstrap["bootstrap_blocks"],
        "median_per_geometry_kendall_tau": trends["median_tau"],
        "positive_direction_geometry_ratio": trends["positive_ratio"],
        "per_geometry_kendall_tau": trends["serialized"],
        "paired_monotonic_rate": paired["monotonic_pair_rate"],
        "sensor_run_count": len(selected),
    }


def direction_result(rows: Sequence[Mapping[str, Any]], sweep: str) -> Dict[str, Any]:
    severe_levels = set(LEVELS[sweep][2:])
    selected = [row for row in rows if row["sweep_type"] == sweep and row["level"] in severe_levels]
    medians = finite_values(selected, "primary_direction_axis_alignment_median")
    p10s = finite_values(selected, "primary_direction_axis_alignment_p10")
    result = {
        "sweep_type": sweep,
        "severe_levels": ",".join(LEVELS[sweep][2:]),
        "primary_direction_axis_alignment_median": float(np.median(medians)) if medians.size else float("nan"),
        "primary_direction_axis_alignment_p10": float(np.percentile(p10s, 10.0)) if p10s.size else float("nan"),
        "primary_direction_stable_rate": mean_field(selected, "primary_direction_stable_rate"),
        "degeneracy_trigger_rate": mean_field(selected, "degeneracy_trigger_rate"),
        "actionable_direction_rate": mean_field(selected, "actionable_direction_rate"),
    }
    for level in LEVELS[sweep][2:]:
        level_rows = [row for row in selected if row["level"] == level]
        result[f"{level}_trigger_rate"] = mean_field(level_rows, "degeneracy_trigger_rate")
    return result


def open_control_result(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    selected = [row for row in rows if row["level"] == "OC"]
    return {
        "sensor_run_count": len(selected),
        "degeneracy_false_positive_rate": mean_field(selected, "degeneracy_trigger_rate"),
        "actionable_direction_false_positive_rate": mean_field(selected, "actionable_direction_rate"),
    }


def mechanism_result(
    root: Path,
    rows: Sequence[Mapping[str, Any]],
    audit_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    geometry_groups = group_sensor_levels(rows, "geometry", LEVELS["geometry"])
    geometry_passed = 0
    geometry_axis_passed = 0
    for levels in geometry_groups.values():
        nested = all(bool(levels[level]["parent_measurement_subset_valid"]) for level in LEVELS["geometry"])
        psd = all(bool(levels[level]["psd_increment_valid"]) for level in LEVELS["geometry"])
        values = [float(levels[level]["axis_information_raw_median"]) for level in LEVELS["geometry"]]
        monotonic = all(values[index] + 1.0e-8 >= values[index + 1] for index in range(3))
        geometry_passed += int(nested and psd and monotonic)
        geometry_axis_passed += int(monotonic)

    observation_groups = group_sensor_levels(rows, "observation", LEVELS["observation"])
    observation_passed = 0
    observation_nested = 0
    for levels in observation_groups.values():
        fractions = [float(levels[level]["realized_axial_point_fraction"]) for level in LEVELS["observation"]]
        information = [
            float(levels[level]["axis_information_normalized_median"]) for level in LEVELS["observation"]
        ]
        outputs = {
            level: load_npz(root / str(levels[level]["observations_path"])) for level in LEVELS["observation"]
        }
        masks = [outputs[level]["retained_axial_candidate_mask"] for level in LEVELS["observation"]]
        nested = bool(
            np.all(~masks[3] | masks[2])
            and np.all(~masks[2] | masks[1])
            and np.all(~masks[1] | masks[0])
        )
        observation_nested += int(nested)
        observation_passed += int(
            nested
            and all(fractions[index] > fractions[index + 1] for index in range(3))
            and all(information[index] > information[index + 1] for index in range(3))
        )
    delta_minimum = min((float(row["delta_H_min_eigenvalue"]) for row in audit_rows), default=float("nan"))
    return {
        "geometry_pair_count": len(geometry_groups),
        "geometry_pairs_passed": geometry_passed,
        "geometry_axis_information_monotonic_pairs": geometry_axis_passed,
        "measurement_sets_strictly_nested": all(
            bool(row["parent_measurement_subset_valid"]) for row in audit_rows
        ),
        "psd_increment_valid": all(bool(row["psd_increment_valid"]) for row in audit_rows),
        "delta_H_min_eigenvalue": delta_minimum,
        "observation_pair_count": len(observation_groups),
        "observation_pairs_passed": observation_passed,
        "observation_nested_pairs": observation_nested,
    }


def evaluate_gates(
    root: Path,
    manifest: Mapping[str, Any],
    detector_results: Sequence[Mapping[str, Any]],
    direction_results: Sequence[Mapping[str, Any]],
    open_control: Mapping[str, Any],
    mechanism: Mapping[str, Any],
    common: Mapping[str, Any],
    lock_verification: Mapping[str, Any],
) -> Dict[str, Any]:
    cleanup_manifest_path = root / "artifacts/current/cleanup_manifest.json"
    cleanup = read_json(cleanup_manifest_path) if cleanup_manifest_path.exists() else {}
    tracked_generated = subprocess.check_output(
        ["git", "ls-files", "data/**", "results/**"], cwd=root, text=True
    ).splitlines()
    tracked_generated = [path for path in tracked_generated if path != "data/.gitkeep"]
    engineering_checks = {
        "full_pytest_passed": bool(
            manifest.get("pytest_provenance") and int(manifest["pytest_provenance"].get("return_code", -1)) == 0
        ),
        "git_status_clean_at_start": bool(manifest["git_status_clean_at_start"]),
        "source_hash_matched": bool(lock_verification.get("source_hash_matched")),
        "config_hash_matched": bool(lock_verification.get("config_hash_matched")),
        "test_sensor_runs": int(manifest["sensor_run_count"]),
        "process_trials_absent": int(manifest["process_trial_count"]) == 0,
        "geometry_measurements_nested": bool(mechanism["measurement_sets_strictly_nested"]),
        "observation_retention_nested": int(mechanism["observation_nested_pairs"])
        == int(mechanism["observation_pair_count"]),
        "empty_subspace_nan_semantics": bool(
            np.isnan(compute_subspace_axis_alignment(None, np.array([1.0, 0.0, 0.0])))
        ),
        "runtime_trigger_has_no_gt_dependency": bool(engineering_specific_tests_present(root)),
        "tracked_generated_files": tracked_generated,
        "cleanup_remaining_cache_files": int(cleanup.get("remaining_cache_files", -1)),
        "cleanup_workspace_bytes": int(cleanup.get("remaining_workspace_bytes", 1 << 60)),
    }
    engineering_pass = bool(
        engineering_checks["full_pytest_passed"]
        and engineering_checks["git_status_clean_at_start"]
        and engineering_checks["source_hash_matched"]
        and engineering_checks["config_hash_matched"]
        and engineering_checks["test_sensor_runs"] == 180
        and engineering_checks["process_trials_absent"]
        and engineering_checks["geometry_measurements_nested"]
        and engineering_checks["observation_retention_nested"]
        and engineering_checks["empty_subspace_nan_semantics"]
        and engineering_checks["runtime_trigger_has_no_gt_dependency"]
        and not tracked_generated
        and engineering_checks["cleanup_remaining_cache_files"] == 0
        and engineering_checks["cleanup_workspace_bytes"] < 30 * 1024 * 1024
    )
    geometry_pass = bool(
        int(mechanism["geometry_pair_count"]) == int(common["gates"]["geometry_mechanism_pairs_required"])
        and int(mechanism["geometry_pairs_passed"]) == int(mechanism["geometry_pair_count"])
        and bool(mechanism["measurement_sets_strictly_nested"])
        and bool(mechanism["psd_increment_valid"])
    )
    observation_pass = bool(
        int(mechanism["observation_pairs_passed"])
        >= int(common["gates"]["observation_mechanism_pairs_required"])
    )
    detector_checks = {
        row["sweep_type"]: detector_gate_pass(row, common) for row in detector_results
    }
    direction_checks = {
        row["sweep_type"]: direction_gate_pass(row, common) for row in direction_results
    }
    control_pass = bool(
        float(open_control["degeneracy_false_positive_rate"])
        <= float(common["gates"]["open_control_false_positive_max"])
        and float(open_control["actionable_direction_false_positive_rate"])
        <= float(common["gates"]["open_control_false_positive_max"])
    )
    detector_pass = all(detector_checks.values()) and all(direction_checks.values()) and control_pass
    return {
        "engineering": "ENGINEERING_PASS" if engineering_pass else "ENGINEERING_FAIL",
        "geometry_mechanism": "GEOMETRY_MECHANISM_PASS" if geometry_pass else "GEOMETRY_MECHANISM_FAIL",
        "observation_mechanism": "OBSERVATION_MECHANISM_PASS" if observation_pass else "OBSERVATION_MECHANISM_FAIL",
        "detector": "DETECTOR_PASS" if detector_pass else "DETECTOR_FAIL",
        "checks": {
            "engineering": engineering_checks,
            "mechanism": dict(mechanism),
            "detector": detector_checks,
            "direction": direction_checks,
            "open_control": dict(open_control),
        },
    }


def detector_gate_pass(result: Mapping[str, Any], common: Mapping[str, Any]) -> bool:
    gates = common["gates"]
    return bool(
        float(result["spearman_rho"]) >= float(gates["detector_severity_rho_min"])
        and float(result["bootstrap_ci_low"]) > 0.0
        and float(result["median_per_geometry_kendall_tau"]) >= float(gates["detector_kendall_median_min"])
        and float(result["positive_direction_geometry_ratio"])
        >= float(gates["detector_positive_geometry_ratio_min"])
        and float(result["paired_monotonic_rate"]) >= float(gates["detector_paired_monotonic_rate_min"])
    )


def direction_gate_pass(result: Mapping[str, Any], common: Mapping[str, Any]) -> bool:
    gates = common["gates"]
    level_prefix = "L" if result["sweep_type"] == "geometry" else "O"
    return bool(
        float(result["primary_direction_axis_alignment_median"])
        >= float(gates["direction_alignment_median_min"])
        and float(result["primary_direction_axis_alignment_p10"])
        >= float(gates["direction_alignment_p10_min"])
        and float(result["primary_direction_stable_rate"]) >= float(gates["direction_stable_rate_min"])
        and float(result["actionable_direction_rate"]) >= float(gates["actionable_direction_rate_min"])
        and float(result[f"{level_prefix}4_trigger_rate"])
        >= float(gates[f"severe_{level_prefix.lower()}4_trigger_rate_min"])
        and float(result[f"{level_prefix}3_trigger_rate"])
        >= float(gates[f"severe_{level_prefix.lower()}3_trigger_rate_min"])
    )


def authorization_decisions(gates: Mapping[str, Any]) -> Dict[str, bool]:
    """Issue only the authorization supported by all frozen Stage 2A gates."""

    return {
        "WEAK_UPDATE_AUTHORIZED": bool(
            gates["engineering"] == "ENGINEERING_PASS"
            and gates["geometry_mechanism"] == "GEOMETRY_MECHANISM_PASS"
            and gates["observation_mechanism"] == "OBSERVATION_MECHANISM_PASS"
            and gates["detector"] == "DETECTOR_PASS"
        ),
        "RISK_WARNING_AUTHORIZED": False,
    }


def lock_detector_analysis(root: Path, development_run_dir: Path) -> Dict[str, Any]:
    root = Path(root).resolve()
    run_dir = Path(development_run_dir).resolve()
    expected_parent = (root / "results/detector_stage2a/development").resolve()
    if expected_parent not in run_dir.parents:
        raise ValueError("--lock-detector accepts only a Stage 2A development run")
    output = run_dir / "detector_lock.json"
    if output.exists():
        raise FileExistsError("detector_lock.json is immutable and already exists")
    manifest = read_json(run_dir / "manifests/development_manifest.json")
    if int(manifest["sensor_run_count"]) != 468:
        raise ValueError("development run is incomplete")
    threshold = read_json(run_dir / "odi_threshold_calibration.json")
    common = load_yaml(root / "configs/redesign/detector_stage2a_common.yaml")
    development = normalize_phase_config(
        load_yaml(root / "configs/redesign/detector_stage2a_development.yaml")
    )
    reserved = normalize_phase_config(load_yaml(root / "configs/redesign/detector_stage2a_test.yaml"))
    lock = build_detector_lock(root, run_dir, threshold, manifest, common, development, reserved)
    write_json(output, lock)
    return lock


def analyze_existing_stage2a(root: Path, run_dir: Path) -> Dict[str, Any]:
    root = Path(root).resolve()
    result_run = Path(run_dir).resolve()
    manifests = list((result_run / "manifests").glob("*_manifest.json"))
    if len(manifests) != 1:
        raise FileNotFoundError("analyze-only requires one Stage 2A manifest")
    manifest = read_json(manifests[0])
    manifest.setdefault("analysis_history", []).append(analysis_record(root))
    manifest["analysis_git_commit"] = git_commit(root)
    write_json(manifests[0], manifest)
    return manifest


def build_level_summary(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["sweep_type"]), str(row["level"]))].append(row)
    output = []
    for (sweep, level), values in sorted(grouped.items()):
        output.append(
            {
                "sweep_type": sweep,
                "level": level,
                "sensor_run_count": len(values),
                "ODI_trans_median": median_field(values, "ODI_trans_median"),
                "axis_information_raw_median": median_field(values, "axis_information_raw_median"),
                "axis_information_normalized_median": median_field(values, "axis_information_normalized_median"),
                "primary_direction_axis_alignment_median": median_field(
                    values, "primary_direction_axis_alignment_median"
                ),
                "degeneracy_trigger_rate": mean_field(values, "degeneracy_trigger_rate"),
                "actionable_direction_rate": mean_field(values, "actionable_direction_rate"),
            }
        )
    return output


def severity_rows(
    rows: Sequence[Mapping[str, Any]], sweep: str, levels: Sequence[str]
) -> List[Dict[str, Any]]:
    severity = {level: index + 1 for index, level in enumerate(levels)}
    output = []
    for source in rows:
        if source["sweep_type"] != sweep or source["level"] not in severity:
            continue
        row = dict(source)
        row["severity"] = severity[str(row["level"])]
        output.append(row)
    return output


def per_geometry_trends(
    rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str
) -> Dict[str, Any]:
    grouped: Dict[int, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["geometry_seed"])].append(row)
    values = {}
    for seed, group in grouped.items():
        values[seed] = float(
            kendalltau(
                [float(row[x_field]) for row in group],
                [float(row[y_field]) for row in group],
            ).statistic
        )
    finite_tau = finite(np.asarray(list(values.values()), dtype=float))
    return {
        "median_tau": float(np.median(finite_tau)) if finite_tau.size else float("nan"),
        "positive_ratio": float(np.mean(finite_tau > 0.0)) if finite_tau.size else float("nan"),
        "serialized": ";".join(f"{seed}:{values[seed]:.9g}" for seed in sorted(values)),
    }


def group_sensor_levels(
    rows: Sequence[Mapping[str, Any]], sweep: str, levels: Sequence[str]
) -> Dict[tuple[int, int], Dict[str, Mapping[str, Any]]]:
    output: Dict[tuple[int, int], Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["sweep_type"] == sweep and row["level"] in levels:
            output[(int(row["geometry_seed"]), int(row["sensor_seed"]))][str(row["level"])] = row
    return {key: value for key, value in output.items() if all(level in value for level in levels)}


def write_gate_outputs(
    result_run: Path,
    gates: Mapping[str, Any],
    authorizations: Mapping[str, bool],
    detector_results: Sequence[Mapping[str, Any]],
    direction_results: Sequence[Mapping[str, Any]],
    open_control: Mapping[str, Any],
) -> None:
    rows = [{"gate": key, "status": value} for key, value in gates.items() if key != "checks"]
    rows.extend({"gate": key, "status": value} for key, value in authorizations.items())
    write_csv(result_run / "tables/gate_summary.csv", rows)
    lines = [
        "# Detector Consolidation Stage 2A Gate Report",
        "",
        f"- Engineering: **{gates['engineering']}**",
        f"- Geometry Mechanism: **{gates['geometry_mechanism']}**",
        f"- Observation Mechanism: **{gates['observation_mechanism']}**",
        f"- Detector: **{gates['detector']}**",
        f"- WEAK_UPDATE_AUTHORIZED: **{str(authorizations['WEAK_UPDATE_AUTHORIZED']).lower()}**",
        "- RISK_WARNING_AUTHORIZED: **false** (fixed; risk prediction is paused)",
        "",
        "## ODI severity detection",
        "",
    ]
    for row in detector_results:
        lines.append(
            f"- {row['sweep_type']}: rho={row['spearman_rho']:.6g}, "
            f"CI=[{row['bootstrap_ci_low']:.6g}, {row['bootstrap_ci_high']:.6g}], "
            f"median tau={row['median_per_geometry_kendall_tau']:.6g}, "
            f"positive ratio={row['positive_direction_geometry_ratio']:.6g}, "
            f"paired rate={row['paired_monotonic_rate']:.6g}."
        )
    lines.extend(["", "## Primary direction", ""])
    for row in direction_results:
        lines.append(
            f"- {row['sweep_type']}: alignment median={row['primary_direction_axis_alignment_median']:.6g}, "
            f"p10={row['primary_direction_axis_alignment_p10']:.6g}, "
            f"stable rate={row['primary_direction_stable_rate']:.6g}, "
            f"actionable rate={row['actionable_direction_rate']:.6g}."
        )
    lines.extend(
        [
            "",
            f"Open Control degeneracy false-positive rate: {open_control['degeneracy_false_positive_rate']:.6g}.",
            f"Open Control actionable-direction false-positive rate: {open_control['actionable_direction_false_positive_rate']:.6g}.",
            "",
            "Stage 2A does not run toy LIO or process trials, does not predict drift magnitude, does not implement a weak-subspace update, and does not integrate FAST-LIO2.",
            "",
        ]
    )
    (result_run / "reports/detector_stage2a_gate_report.md").write_text("\n".join(lines), encoding="utf-8")
    (result_run / "reports/detector_stage2a_reproducibility_report.md").write_text(
        "# Stage 2A Reproducibility\n\n"
        "The test used a committed detector lock, frozen Development Open Control ODI threshold, "
        "disjoint geometry/sensor seeds, and a clean source/config hash match.\n",
        encoding="utf-8",
    )


def build_development_report(
    manifest: Mapping[str, Any],
    detector_results: Sequence[Mapping[str, Any]],
    direction_results: Sequence[Mapping[str, Any]],
    open_control: Mapping[str, Any],
    mechanism: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "# Detector Stage 2A Development Report",
            "",
            f"- Sensor runs: {manifest['sensor_run_count']}",
            f"- Frozen-candidate ODI threshold: {manifest['odi_trigger_threshold']}",
            f"- Geometry mechanism pairs: {mechanism['geometry_pairs_passed']}/{mechanism['geometry_pair_count']}",
            f"- Observation mechanism pairs: {mechanism['observation_pairs_passed']}/{mechanism['observation_pair_count']}",
            f"- Open Control false-positive rate: {open_control['degeneracy_false_positive_rate']}",
            "",
            "Development diagnostics do not issue authorization and do not evaluate reserved test seeds.",
            "",
        ]
    )


def export_current_artifacts(
    root: Path,
    result_run: Path,
    lock_path: Path,
    manifest: Mapping[str, Any],
) -> None:
    target = root / "artifacts/current/detector_stage2a"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lock_path, target / "detector_lock.json")
    for source in [
        result_run / "reports/detector_stage2a_gate_report.md",
        result_run / "reports/detector_stage2a_reproducibility_report.md",
        result_run / "tables/detector_results.csv",
        result_run / "tables/direction_results.csv",
        result_run / "tables/mechanism_summary.csv",
        result_run / "tables/gate_summary.csv",
    ]:
        shutil.copy2(source, target / source.name)
    write_json(target / "test_manifest.json", manifest)


def analysis_record(root: Path) -> Dict[str, Any]:
    return {
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_git_commit": git_commit(root),
        "analysis_source_tree_sha256": compute_source_tree_hash(detector_source_paths(root)),
    }


def engineering_specific_tests_present(root: Path) -> bool:
    required = [
        "tests/test_empty_weak_subspace_semantics.py",
        "tests/test_detector_no_gt_dependency.py",
        "tests/test_nested_geometry_measurement_ids.py",
        "tests/test_nested_geometry_psd_increment.py",
    ]
    return all((root / path).exists() for path in required)


def scalar_string(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(np.asarray(value).item())


def finite(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return array[np.isfinite(array)]


def finite_values(rows: Sequence[Mapping[str, Any]], field: str) -> np.ndarray:
    return finite(np.asarray([float(row[field]) for row in rows], dtype=float))


def median_field(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = finite_values(rows, field)
    return float(np.median(values)) if values.size else float("nan")


def mean_field(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = finite_values(rows, field)
    return float(np.mean(values)) if values.size else float("nan")
