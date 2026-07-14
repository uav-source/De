"""Metric Redesign Stage 1 orchestration and independent-sample analysis."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import yaml
from scipy.stats import spearmanr

from degen_detector.odi_tracker import compute_metrics_for_sequence
from minibench.motion_simulator import save_motion_measurements, simulate_motion_measurements
from minibench.observation_simulator import save_observations, simulate_sequence_observations
from minibench.scene_generator import (
    generate_open_control,
    generate_straight_tunnel,
    load_scene_config,
    save_sequence,
)
from minibench.toy_lio import load_toy_lio_config, resolve_process_noise_parameters, run_toy_lio, save_pose_est_tum


METRIC_FIELDS = [
    "ODI",
    "ODI_trans",
    "AIS_trans_normalized",
    "lambda_min_trans_normalized",
    "condition_number_trans",
    "weak_trans_subspace_alignment",
]
EXPECTED_DIRECTIONS = {
    "ODI": 1,
    "ODI_trans": 1,
    "AIS_trans_normalized": -1,
    "lambda_min_trans_normalized": -1,
    "condition_number_trans": 1,
    "weak_trans_subspace_alignment": 1,
}


def run_stage1(
    root: Path,
    mode: str,
    sweep_config_path: Path,
    detector_config_path: Path,
    motion_config_path: Path,
) -> Dict[str, Any]:
    started = time.time()
    sweep = load_yaml(sweep_config_path)
    detector = load_yaml(detector_config_path)
    motion_raw = load_yaml(motion_config_path)
    data_root = root / "data/metric_redesign_stage1"
    result_root = root / "results/metric_redesign_stage1"
    tables_root = result_root / "tables"
    manifests_root = result_root / "manifests"
    reports_root = result_root / "reports"
    for directory in [data_root, tables_root, manifests_root, reports_root]:
        directory.mkdir(parents=True, exist_ok=True)

    if mode == "analyze-only":
        process_rows = read_csv(tables_root / "process_trial_summary.csv")
        if not process_rows:
            raise FileNotFoundError("analyze-only requires process_trial_summary.csv")
        analysis = analyze_stage1(data_root, result_root, sweep, process_rows)
        manifest = build_manifest(
            root,
            mode,
            sweep_config_path,
            detector_config_path,
            motion_config_path,
            analysis,
            time.time() - started,
        )
        write_json(manifests_root / "stage1_manifest.json", manifest)
        return manifest

    geometry_seeds = [int(value) for value in sweep["geometry_seeds"]]
    sensor_seeds = [int(value) for value in sweep["sensor_seeds"]]
    process_seeds = [int(value) for value in sweep["process_seeds"]]
    open_seeds = [int(value) for value in sweep["open_control_geometry_seeds"]]
    if mode == "quick":
        geometry_seeds = geometry_seeds[:1]
        sensor_seeds = sensor_seeds[:1]
        process_seeds = process_seeds[:2]
        open_seeds = open_seeds[:1]

    sequence_specs = build_sequence_specs(sweep, geometry_seeds, open_seeds)
    process_rows: List[Dict[str, Any]] = []
    for spec in sequence_specs:
        sequence_dir = data_root / spec["sequence_id"]
        sequence_dir.mkdir(parents=True, exist_ok=True)
        resolved_config_path = sequence_dir / "resolved_scene_config.yaml"
        resolved_config_path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
        resolved = load_scene_config(resolved_config_path)
        sequence = generate_open_control(resolved) if spec["scene_family"] == "OC" else generate_straight_tunnel(resolved)
        save_sequence(sequence, sequence_dir)

        for sensor_seed in sensor_seeds:
            sensor_dir = sequence_dir / f"sensor_{sensor_seed:03d}"
            sensor_dir.mkdir(parents=True, exist_ok=True)
            observations = simulate_sequence_observations(sequence_dir, detector_config_path, sensor_seed=sensor_seed)
            save_observations(observations, sensor_dir / "observations.npz")
            metrics = compute_metrics_for_sequence(observations, detector)
            write_structured_csv(metrics, sensor_dir / "metrics.csv")
            write_json(
                sensor_dir / "observation_metadata.json",
                {
                    "sequence_id": spec["sequence_id"],
                    "geometry_seed": spec["geometry_seed"],
                    "sensor_seed": sensor_seed,
                    "point_count_per_frame": int(observations["packed_J"].shape[1]),
                    "frames": int(observations["packed_J"].shape[0]),
                    "detector_config": relative(root, detector_config_path),
                    "observation_sha256": sha256_file(sensor_dir / "observations.npz"),
                },
            )

            family = str(spec["scene_family"])
            toy_config = load_toy_lio_config(motion_raw)
            motion_parameters = resolve_process_noise_parameters(family, toy_config)
            for process_seed in process_seeds:
                motion = simulate_motion_measurements(
                    observations["pose_gt"], process_seed, motion_parameters, axes=observations["axis_per_frame"]
                )
                motion_path = result_root / "motion" / spec["sequence_id"] / f"sensor_{sensor_seed:03d}" / f"process_{process_seed}.npz"
                save_motion_measurements(motion, motion_path)
                result = run_toy_lio(
                    sequence_dir,
                    detector,
                    toy_config,
                    motion_measurements=motion,
                    process_seed=process_seed,
                    observations_path=sensor_dir / "observations.npz",
                )
                trajectory_path = (
                    result_root
                    / "trajectories"
                    / spec["sequence_id"]
                    / f"sensor_{sensor_seed:03d}"
                    / f"process_{process_seed}.tum"
                )
                save_pose_est_tum(result["poses"], trajectory_path)
                path_length = cumulative_path_length(observations["pose_gt"][:, 1:4])
                summary = result["summary"]
                process_rows.append(
                    {
                        "sequence_id": spec["sequence_id"],
                        "scene_family": family,
                        "level": spec["difficulty"],
                        "geometry_seed": spec["geometry_seed"],
                        "sensor_seed": sensor_seed,
                        "process_seed": process_seed,
                        "final_translation_error": summary["final_translation_error"],
                        "final_axis_error": summary["final_axis_error"],
                        "final_cross_error": summary["final_cross_error"],
                        "mean_axis_error": summary["mean_axis_error"],
                        "mean_cross_error": summary["mean_cross_error"],
                        "axis_drift_rate": summary["final_axis_error"] / max(path_length, 1.0e-9),
                        "trajectory_path": relative(root, trajectory_path),
                        "motion_path": relative(root, motion_path),
                    }
                )

    write_csv(tables_root / "process_trial_summary.csv", process_rows)
    analysis = analyze_stage1(data_root, result_root, sweep, process_rows)
    manifest = build_manifest(
        root,
        mode,
        sweep_config_path,
        detector_config_path,
        motion_config_path,
        analysis,
        time.time() - started,
    )
    write_json(manifests_root / "stage1_manifest.json", manifest)
    return manifest


def build_sequence_specs(
    sweep: Mapping[str, Any], geometry_seeds: Sequence[int], open_seeds: Sequence[int]
) -> List[Dict[str, Any]]:
    scene = sweep["scene"]
    specs: List[Dict[str, Any]] = []
    seed_to_index = {seed: index + 1 for index, seed in enumerate(sweep["geometry_seeds"])}
    for seed in open_seeds:
        index = seed_to_index[int(seed)]
        specs.append(
            {
                "sequence_id": f"OC-L0-G{index:02d}",
                "scene_family": "OC",
                "difficulty": "L0",
                "seed_id": f"G{index:02d}",
                "motion_id": "M1",
                "random_seed": int(seed),
                "geometry_seed": int(seed),
                "axis": [1.0, 0.0, 0.0],
                "length_m": float(scene["open_length_m"]),
                "frames": int(scene["frames"]),
                "dt_s": float(scene["dt_s"]),
                "expected_degeneracy": "low",
                "scientific_role": "stage1_open_control",
                "scene": {
                    "bounds_m": scene["open_bounds_m"],
                    "box_count": int(scene["open_box_count"]),
                },
            }
        )
    for level, level_config in sweep["levels"].items():
        for seed in geometry_seeds:
            index = seed_to_index[int(seed)]
            specs.append(
                {
                    "sequence_id": f"ST-{level}-G{index:02d}",
                    "scene_family": "ST",
                    "difficulty": level,
                    "seed_id": f"G{index:02d}",
                    "motion_id": "M1",
                    "random_seed": int(seed),
                    "geometry_seed": int(seed),
                    "axis": [1.0, 0.0, 0.0],
                    "tunnel_length_m": float(scene["tunnel_length_m"]),
                    "width_m": float(scene["width_m"]),
                    "height_m": float(scene["height_m"]),
                    "frames": int(scene["frames"]),
                    "dt_s": float(scene["dt_s"]),
                    "axial_support_fraction": float(level_config["axial_support_fraction"]),
                    "axial_patch_count": int(scene["axial_patch_count"]),
                    "expected_degeneracy": f"continuous_axial_support_{level}",
                    "scientific_role": "stage1_continuous_st_sweep",
                    "scene": {"finite_plane_patches": True},
                }
            )
    return specs


def analyze_stage1(
    data_root: Path,
    result_root: Path,
    sweep: Mapping[str, Any],
    process_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    tables_root = result_root / "tables"
    process_by_sensor: Dict[Tuple[str, int], List[Mapping[str, Any]]] = defaultdict(list)
    for row in process_rows:
        process_by_sensor[(str(row["sequence_id"]), int(row["sensor_seed"]))].append(row)
    trial_aggregates = aggregate_process_trial_rows(process_rows)

    sensor_rows: List[Dict[str, Any]] = []
    for sequence_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
        metadata = json.loads((sequence_dir / "scene_metadata.json").read_text(encoding="utf-8"))
        for sensor_dir in sorted(sequence_dir.glob("sensor_*")):
            sensor_seed = int(sensor_dir.name.split("_")[1])
            metric_rows = read_csv(sensor_dir / "metrics.csv")
            trials = process_by_sensor.get((sequence_dir.name, sensor_seed), [])
            if not metric_rows or not trials:
                continue
            aggregate = trial_aggregates[(sequence_dir.name, sensor_seed)]
            row: Dict[str, Any] = {
                "sequence_id": sequence_dir.name,
                "scene_family": metadata["scene_family"],
                "level": metadata["difficulty"],
                "geometry_seed": int(metadata["geometry_seed"]),
                "sensor_seed": sensor_seed,
                **aggregate,
            }
            for field in METRIC_FIELDS + ["lambda_min", "condition_number", "weak_trans_subspace_dim"]:
                values = finite_values(metric_rows, field)
                row[f"{field}_median"] = float(np.median(values)) if values.size else float("nan")
            sensor_rows.append(row)
    write_csv(tables_root / "sensor_run_summary.csv", sensor_rows)

    level_rows = build_level_summary(sensor_rows)
    write_csv(tables_root / "level_summary.csv", level_rows)
    correlation_rows = build_correlation_summary(sensor_rows, sweep)
    write_csv(tables_root / "correlation_summary.csv", correlation_rows)
    window_rows = build_window_aggregate(data_root, result_root, process_rows)
    write_csv(tables_root / "window_aggregate.csv", window_rows)
    gate = evaluate_gate(sensor_rows, level_rows, correlation_rows, sweep)
    report_path = result_root / "reports/stage1_gate_report.md"
    report_path.write_text(build_gate_report(gate, level_rows, correlation_rows, sensor_rows), encoding="utf-8")
    return {
        "sequence_count": len({row["sequence_id"] for row in sensor_rows}),
        "sensor_run_count": len(sensor_rows),
        "process_trial_count": len(process_rows),
        "window_row_count": len(window_rows),
        "scientific_gate": gate["decision"],
        "gate_checks": gate["checks"],
        "output_paths": [
            str(tables_root / "sensor_run_summary.csv"),
            str(tables_root / "process_trial_summary.csv"),
            str(tables_root / "window_aggregate.csv"),
            str(tables_root / "level_summary.csv"),
            str(tables_root / "correlation_summary.csv"),
            str(report_path),
        ],
    }


def aggregate_process_trial_rows(
    process_rows: Sequence[Mapping[str, Any]],
) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """Return exactly one drift distribution summary per independent sensor run."""

    grouped: Dict[Tuple[str, int], List[Mapping[str, Any]]] = defaultdict(list)
    for row in process_rows:
        grouped[(str(row["sequence_id"]), int(row["sensor_seed"]))].append(row)
    output: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for key, rows in grouped.items():
        drift = np.asarray([float(row["axis_drift_rate"]) for row in rows], dtype=float)
        final_axis = np.asarray([float(row["final_axis_error"]) for row in rows], dtype=float)
        output[key] = {
            "process_trial_count": len(rows),
            "axis_drift_rate_median": float(np.median(drift)),
            "axis_drift_rate_mean": float(np.mean(drift)),
            "axis_drift_rate_iqr": iqr(drift),
            "axis_drift_rate_mad": mad(drift),
            "final_axis_error_median": float(np.median(final_axis)),
        }
    return output


def build_level_summary(sensor_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in sensor_rows:
        grouped[str(row["level"])].append(row)
    output = []
    for level in ["L0", "L1", "L2", "L3", "L4"]:
        rows = grouped.get(level, [])
        if not rows:
            continue
        output.append(
            {
                "level": level,
                "independent_sensor_runs": len(rows),
                "ODI_trans_median": median_field(rows, "ODI_trans_median"),
                "lambda_min_trans_normalized_median": median_field(rows, "lambda_min_trans_normalized_median"),
                "weak_trans_subspace_alignment_median": median_field(rows, "weak_trans_subspace_alignment_median"),
                "axis_drift_rate_median": median_field(rows, "axis_drift_rate_median"),
                "ODI_median": median_field(rows, "ODI_median"),
                "AIS_trans_normalized_median": median_field(rows, "AIS_trans_normalized_median"),
                "condition_number_trans_median": median_field(rows, "condition_number_trans_median"),
            }
        )
    return output


def build_correlation_summary(
    sensor_rows: Sequence[Mapping[str, Any]], sweep: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    st_rows = [row for row in sensor_rows if row["scene_family"] == "ST"]
    stats = sweep["statistics"]
    output = []
    for field in METRIC_FIELDS:
        x_name = f"{field}_median"
        x = np.asarray([float(row[x_name]) for row in st_rows], dtype=float)
        y = np.asarray([float(row["axis_drift_rate_median"]) for row in st_rows], dtype=float)
        valid = np.isfinite(x) & np.isfinite(y)
        rho = safe_spearman(x[valid], y[valid])
        ci_low, ci_high = block_bootstrap_spearman(
            [row for index, row in enumerate(st_rows) if valid[index]],
            x_name,
            "axis_drift_rate_median",
            int(stats["bootstrap_samples"]),
            int(stats["bootstrap_seed"]),
        )
        seed_rhos = []
        for sensor_seed in sorted({int(row["sensor_seed"]) for row in st_rows}):
            subset = [row for row in st_rows if int(row["sensor_seed"]) == sensor_seed]
            seed_rhos.append(safe_spearman_fields(subset, x_name, "axis_drift_rate_median"))
        expected = EXPECTED_DIRECTIONS[field]
        direction_ok = bool(np.isfinite(rho) and np.sign(rho) == expected)
        stable = bool(seed_rhos and all(np.isfinite(value) and np.sign(value) == expected for value in seed_rhos))
        target = float(stats["target_abs_rho"])
        weak_boundary = float(stats["weak_effect_boundary"])
        ci_direction_ok = ci_low > weak_boundary if expected > 0 else ci_high < -weak_boundary
        output.append(
            {
                "metric_name": field,
                "target": "axis_drift_rate_median",
                "expected_direction": "positive" if expected > 0 else "negative",
                "spearman_rho": rho,
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "independent_sensor_runs": int(np.sum(valid)),
                "direction_matches": direction_ok,
                "seed_direction_stable": stable,
                "passes_abs_rho": bool(np.isfinite(rho) and abs(rho) >= target),
                "passes_ci_direction": bool(ci_direction_ok),
                "passes_metric_gate": bool(direction_ok and stable and abs(rho) >= target and ci_direction_ok),
                "sensor_seed_rhos": ";".join(format_float(value) for value in seed_rhos),
            }
        )
    return output


def block_bootstrap_spearman(
    rows: Sequence[Mapping[str, Any]],
    x_field: str,
    y_field: str,
    samples: int,
    seed: int,
) -> Tuple[float, float]:
    blocks: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        blocks[str(row["sequence_id"])].append(row)
    keys = sorted(blocks)
    if len(keys) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(samples):
        chosen = rng.choice(keys, size=len(keys), replace=True)
        sampled: List[Mapping[str, Any]] = []
        for key in chosen:
            sampled.extend(blocks[str(key)])
        rho = safe_spearman_fields(sampled, x_field, y_field)
        if np.isfinite(rho):
            values.append(rho)
    if not values:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def evaluate_gate(
    sensor_rows: Sequence[Mapping[str, Any]],
    level_rows: Sequence[Mapping[str, Any]],
    correlation_rows: Sequence[Mapping[str, Any]],
    sweep: Mapping[str, Any],
) -> Dict[str, Any]:
    by_level = {str(row["level"]): row for row in level_rows}
    levels_present = all(level in by_level for level in ["L1", "L2", "L3", "L4"])
    lambdas = [float(by_level[level]["lambda_min_trans_normalized_median"]) for level in ["L1", "L2", "L3", "L4"]] if levels_present else []
    odis = [float(by_level[level]["ODI_trans_median"]) for level in ["L1", "L2", "L3", "L4"]] if levels_present else []
    alignments = [float(by_level[level]["weak_trans_subspace_alignment_median"]) for level in ["L2", "L3", "L4"]] if levels_present else []
    oc_rows = [row for row in sensor_rows if row["scene_family"] == "OC"]
    false_triggers = [
        float(row["weak_trans_subspace_alignment_median"]) >= float(sweep["statistics"]["weak_alignment_target"])
        and float(row["weak_trans_subspace_dim_median"]) > 0.0
        for row in oc_rows
    ]
    oc_ratio = float(np.mean(false_triggers)) if false_triggers else float("nan")
    metric_pass = any(bool(row["passes_metric_gate"]) for row in correlation_rows if row["metric_name"] != "ODI")
    checks = {
        "all_levels_present": levels_present,
        "lambda_strictly_decreases": bool(levels_present and all(lambdas[i] > lambdas[i + 1] for i in range(3))),
        "lambda_not_all_zero": bool(lambdas and any(value > 0.0 for value in lambdas)),
        "ODI_trans_increases": bool(levels_present and all(odis[i] < odis[i + 1] for i in range(3))),
        "weak_alignment_L2_L4": bool(alignments and all(value >= float(sweep["statistics"]["weak_alignment_target"]) for value in alignments)),
        "oc_false_trigger_ratio": oc_ratio,
        "oc_false_trigger_pass": bool(np.isfinite(oc_ratio) and oc_ratio <= float(sweep["statistics"]["oc_false_trigger_max"])),
        "at_least_one_redesigned_metric_passes": metric_pass,
    }
    required = [
        checks["all_levels_present"],
        checks["lambda_strictly_decreases"],
        checks["lambda_not_all_zero"],
        checks["ODI_trans_increases"],
        checks["weak_alignment_L2_L4"],
        checks["oc_false_trigger_pass"],
        checks["at_least_one_redesigned_metric_passes"],
    ]
    return {"decision": "PASS" if all(required) else "NO-GO", "checks": checks}


def build_gate_report(
    gate: Mapping[str, Any],
    level_rows: Sequence[Mapping[str, Any]],
    correlation_rows: Sequence[Mapping[str, Any]],
    sensor_rows: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# Metric Redesign Stage 1 Gate Report",
        "",
        f"Scientific decision: **{gate['decision']}**.",
        "",
        "Execution success and scientific acceptance are separate. A NO-GO does not indicate a pipeline failure.",
        "",
        "## Independent-sample accounting",
        "",
        f"- Geometry sequences: {len({row['sequence_id'] for row in sensor_rows})}",
        f"- Independent sensor runs: {len(sensor_rows)}",
        "- Process trials are aggregated within each sensor run and are not counted as independent ODI samples.",
        "",
        "## Level summary",
        "",
        "| Level | N sensor | ODI_trans median | lambda_min_trans_normalized median | weak-subspace alignment median | axis drift median |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in level_rows:
        lines.append(
            f"| {row['level']} | {row['independent_sensor_runs']} | {format_float(row['ODI_trans_median'])} | "
            f"{format_float(row['lambda_min_trans_normalized_median'])} | "
            f"{format_float(row['weak_trans_subspace_alignment_median'])} | {format_float(row['axis_drift_rate_median'])} |"
        )
    lines.extend(
        [
            "",
            "## Correlation summary",
            "",
            "| Metric | Expected | rho | block bootstrap 95% CI | N | seed direction stable | gate |",
            "|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in correlation_rows:
        lines.append(
            f"| {row['metric_name']} | {row['expected_direction']} | {format_float(row['spearman_rho'])} | "
            f"[{format_float(row['bootstrap_ci_low'])}, {format_float(row['bootstrap_ci_high'])}] | "
            f"{row['independent_sensor_runs']} | {row['seed_direction_stable']} | {row['passes_metric_gate']} |"
        )
    lines.extend(["", "## Gate checks", ""])
    for name, value in gate["checks"].items():
        lines.append(f"- {name}: {value}")
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This stage evaluates finite-patch synthetic geometry and a 6DoF motion-propagation surrogate only. It does not validate ODI, implement a weak-subspace update, or constitute a complete Degen-LIO estimator.",
            "",
        ]
    )
    return "\n".join(lines)


def build_window_aggregate(
    data_root: Path, result_root: Path, process_rows: Sequence[Mapping[str, Any]], window: int = 10
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, int], List[Mapping[str, Any]]] = defaultdict(list)
    for row in process_rows:
        grouped[(str(row["sequence_id"]), int(row["sensor_seed"]))].append(row)
    output = []
    for (sequence_id, sensor_seed), trials in grouped.items():
        gt = np.loadtxt(data_root / sequence_id / "gt.tum")
        axis = load_axis(data_root / sequence_id / "axis.csv")
        metric_rows = read_csv(data_root / sequence_id / f"sensor_{sensor_seed:03d}" / "metrics.csv")
        trajectories = [
            np.loadtxt(
                result_root
                / "trajectories"
                / sequence_id
                / f"sensor_{sensor_seed:03d}"
                / f"process_{int(row['process_seed'])}.tum"
            )
            for row in trials
        ]
        for start in range(0, gt.shape[0] - 1, window):
            end = min(start + window, gt.shape[0] - 1)
            if end <= start:
                continue
            segment_length = cumulative_path_length(gt[start : end + 1, 1:4])
            rates = []
            for trajectory in trajectories:
                error = trajectory[:, 1:4] - gt[:, 1:4]
                projected = np.abs(np.einsum("ij,ij->i", error, axis))
                rates.append(abs(float(projected[end] - projected[start])) / max(segment_length, 1.0e-9))
            metric_slice = metric_rows[start : end + 1]
            output.append(
                {
                    "sequence_id": sequence_id,
                    "sensor_seed": sensor_seed,
                    "window_start": start,
                    "window_end": end,
                    "overlapping": False,
                    "process_trial_count": len(rates),
                    "axis_drift_rate_median": float(np.median(rates)),
                    "ODI_trans_median": median_dict_field(metric_slice, "ODI_trans"),
                    "lambda_min_trans_normalized_median": median_dict_field(metric_slice, "lambda_min_trans_normalized"),
                }
            )
    return output


def build_manifest(
    root: Path,
    mode: str,
    sweep_path: Path,
    detector_path: Path,
    motion_path: Path,
    analysis: Mapping[str, Any],
    runtime: float,
) -> Dict[str, Any]:
    expected = {"quick": (5, 5, 10), "full": (15, 30, 150)}.get(mode)
    actual = (
        int(analysis["sequence_count"]),
        int(analysis["sensor_run_count"]),
        int(analysis["process_trial_count"]),
    )
    missing = []
    if expected is not None and actual != expected:
        missing.append(f"expected_counts={expected};actual_counts={actual}")
    outputs = [relative(root, Path(path)) for path in analysis["output_paths"]]
    return {
        "status": "OK" if not missing else "INCOMPLETE",
        "mode": mode,
        "scientific_gate": analysis["scientific_gate"],
        "git_commit": git_commit(root),
        "config_hashes": {
            relative(root, sweep_path): sha256_file(sweep_path),
            relative(root, detector_path): sha256_file(detector_path),
            relative(root, motion_path): sha256_file(motion_path),
        },
        "geometry_seeds": load_yaml(sweep_path)["geometry_seeds"],
        "sensor_seeds": load_yaml(sweep_path)["sensor_seeds"],
        "process_seeds": load_yaml(sweep_path)["process_seeds"],
        "sequence_count": actual[0],
        "sensor_run_count": actual[1],
        "process_trial_count": actual[2],
        "runtime_seconds": round(float(runtime), 6),
        "input_paths": [relative(root, path) for path in [sweep_path, detector_path, motion_path]],
        "output_paths": outputs,
        "missing_artifacts": missing,
        "gate_checks": analysis["gate_checks"],
    }


def load_axis(path: Path) -> np.ndarray:
    rows = read_csv(path)
    return np.asarray([[float(row["axis_x"]), float(row["axis_y"]), float(row["axis_z"])] for row in rows])


def load_yaml(path: Path) -> Dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_structured_csv(rows: np.ndarray, path: Path) -> None:
    fieldnames = list(rows.dtype.names or [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name].item() for name in fieldnames})


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def finite_values(rows: Sequence[Mapping[str, Any]], field: str) -> np.ndarray:
    values = np.asarray([float(row[field]) for row in rows if field in row], dtype=float)
    return values[np.isfinite(values)]


def median_field(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = finite_values(rows, field)
    return float(np.median(values)) if values.size else float("nan")


def median_dict_field(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    return median_field(rows, field)


def iqr(values: np.ndarray) -> float:
    return float(np.percentile(values, 75.0) - np.percentile(values, 25.0))


def mad(values: np.ndarray) -> float:
    median = float(np.median(values))
    return float(np.median(np.abs(values - median)))


def cumulative_path_length(points: np.ndarray) -> float:
    values = np.asarray(points, dtype=float)
    if values.shape[0] < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(values, axis=0), axis=1)))


def safe_spearman(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 3 or y.size != x.size or np.allclose(x, x[0]) or np.allclose(y, y[0]):
        return float("nan")
    return float(spearmanr(x, y).statistic)


def safe_spearman_fields(rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str) -> float:
    x = np.asarray([float(row[x_field]) for row in rows], dtype=float)
    y = np.asarray([float(row[y_field]) for row in rows], dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    return safe_spearman(x[valid], y[valid])


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
