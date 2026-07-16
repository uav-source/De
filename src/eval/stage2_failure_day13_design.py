"""Preregistered design and immutable trial-plan construction for Day 13."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from eval.analysis_lock import (
    compute_bundle_hash,
    compute_directory_hash,
    git_commit,
    git_status_clean,
    sha256_file,
)
from eval.stage2_failure_day13_seeds import (
    SEED_COUNTS,
    SEED_ROLES,
    SEED_TYPES,
    build_seed_exclusion_manifest,
    scan_historical_seed_sources,
    validate_seed_exclusion_manifest,
)
from eval.synthetic_pipeline_common import load_yaml, read_csv, read_json, write_csv, write_json


DAY13_SCHEMA_VERSION = "stage2_failure_day13_v1"
DAY13_DESIGN_SCHEMA_VERSION = "stage2_failure_day13_design_lock_v1"
DAY13_CONFIG_RELATIVE = Path("configs/stage2_failure/day13_new_seed.yaml")
DAY12_CHECKPOINT = "checkpoint/day12-v3-diagnostic-figures-pass"
DAY12_RUN_RELATIVE = Path(
    "results/stage2_failure_analysis/day12_figures/stage2_failure_day12_figures_v3"
)
DAY13_ARTIFACT_RELATIVE = Path("artifacts/current/stage2_day13_diagnostic")
METHODS = ("huber_full",)
STRESSES = ("clean", "coherent_subhuber_slip", "gross_outlier_control")
SWEEPS = ("geometry", "observation", "open_control")
GEOMETRY_LEVELS = ("L3", "L4")
OBSERVATION_LEVELS = ("O3", "O4")
SECONDARY_STATISTICS = (
    "abs_weak_innovation_z_huber",
    "abs_huber_window_mean",
    "huber_window_energy",
    "huber_dominant_sign_ratio",
    "huber_current_same_sign_run_length",
    "abs_huber_lag1_autocorrelation",
    "abs_huber_skewness",
)
TRIAL_PLAN_FIELDS = (
    "role", "case_id", "sweep", "level", "stress", "geometry_seed",
    "sensor_seed", "process_seed", "method", "expected_frame_count",
)
SEED_MANIFEST_FIELDS = ("role", "seed_type", "index", "nonce", "label", "seed")


def load_and_validate_day13_config(root: Path) -> Mapping[str, Any]:
    config = load_yaml(Path(root).resolve() / DAY13_CONFIG_RELATIVE)
    expected = {
        "mode": "day13_new_seed_diagnostic",
        "schema_version": DAY13_SCHEMA_VERSION,
        "method": "huber_full",
        "calibration_geometry_seed_count": 5,
        "evaluation_geometry_seed_count": 10,
        "calibration_sensor_seed_count": 2,
        "evaluation_sensor_seed_count": 2,
        "calibration_process_seed_count": 2,
        "evaluation_process_seed_count": 2,
        "geometry_levels": list(GEOMETRY_LEVELS),
        "observation_levels": list(OBSERVATION_LEVELS),
        "open_control_level": "OC",
        "stress_regimes": list(STRESSES),
        "primary_statistic": "huber_cusum_max",
        "secondary_statistics": list(SECONDARY_STATISTICS),
        "threshold_quantile": 0.90,
        "threshold_quantile_rule": "nearest_rank",
        "threshold_comparison_operator": ">",
        "bootstrap_repetitions": 5000,
        "bootstrap_seed": 23131,
        "bootstrap_block": "geometry_seed",
        "use_full_sequence": True,
        "frame_limit": None,
        "run_open_control_clean": True,
        "run_coherent_on_open_control": False,
        "run_gross_on_open_control": False,
        "create_stage3_threshold": False,
        "compute_f1": False,
        "compute_detection_delay": False,
        "make_stage2_decision": False,
    }
    if set(config) != set(expected):
        raise ValueError("Day 13 config fields changed")
    for field, value in expected.items():
        if config[field] != value or type(config[field]) is not type(value):
            raise ValueError(f"Day 13 config field changed: {field}")
    return config


def build_trial_plan(seed_lists: Mapping[str, Mapping[str, Sequence[int]]]) -> Sequence[Mapping[str, Any]]:
    rows = []
    for role in SEED_ROLES:
        role_seeds = seed_lists[role]
        for geometry_seed in role_seeds["geometry"]:
            for sensor_seed in role_seeds["sensor"]:
                for process_seed in role_seeds["process"]:
                    case_specs = []
                    for level in GEOMETRY_LEVELS:
                        case_specs.extend(("geometry", level, stress) for stress in STRESSES)
                    for level in OBSERVATION_LEVELS:
                        case_specs.extend(("observation", level, stress) for stress in STRESSES)
                    case_specs.append(("open_control", "OC", "clean"))
                    for sweep, level, stress in case_specs:
                        case_id = (
                            f"day13_{role}_{sweep}_{level}_{stress}_"
                            f"G{int(geometry_seed)}_S{int(sensor_seed)}_P{int(process_seed)}"
                        )
                        rows.append({
                            "role": role,
                            "case_id": case_id,
                            "sweep": sweep,
                            "level": level,
                            "stress": stress,
                            "geometry_seed": int(geometry_seed),
                            "sensor_seed": int(sensor_seed),
                            "process_seed": int(process_seed),
                            "method": "huber_full",
                            "expected_frame_count": 39,
                        })
    validate_trial_plan(rows, seed_lists)
    return rows


def validate_trial_plan(
    rows: Sequence[Mapping[str, Any]],
    seed_lists: Mapping[str, Mapping[str, Sequence[int]]],
) -> None:
    expected_counts = {"calibration": 260, "evaluation": 520}
    keys = set()
    counts = {role: 0 for role in SEED_ROLES}
    for row in rows:
        if set(row) != set(TRIAL_PLAN_FIELDS):
            raise ValueError("Day 13 trial plan schema changed")
        role = str(row["role"])
        if role not in SEED_ROLES:
            raise ValueError("Day 13 trial plan contains an unknown role")
        counts[role] += 1
        if str(row["method"]) != "huber_full" or "oracle" in str(row["method"]).lower():
            raise ValueError("Day 13 method list is not frozen to huber_full")
        sweep, level, stress = str(row["sweep"]), str(row["level"]), str(row["stress"])
        if stress == "axial_correspondence_slip" or stress not in STRESSES:
            raise ValueError("Day 13 trial plan contains an invalid stress")
        if sweep == "open_control":
            if level != "OC" or stress != "clean":
                raise ValueError("Day 13 Open Control must be clean-only")
        elif sweep == "geometry":
            if level not in GEOMETRY_LEVELS:
                raise ValueError("Day 13 geometry level changed")
        elif sweep == "observation":
            if level not in OBSERVATION_LEVELS:
                raise ValueError("Day 13 observation level changed")
        else:
            raise ValueError("Day 13 trial plan contains an invalid sweep")
        for seed_type in SEED_TYPES:
            field = f"{seed_type}_seed"
            if int(row[field]) not in {int(value) for value in seed_lists[role][seed_type]}:
                raise ValueError(f"Day 13 trial plan uses an unlocked {field}")
        if int(row["expected_frame_count"]) != 39:
            raise ValueError("Day 13 requires the complete 39-frame estimator output")
        key = tuple(row[field] for field in TRIAL_PLAN_FIELDS if field != "expected_frame_count")
        if key in keys:
            raise ValueError("Day 13 trial plan contains a duplicate case")
        keys.add(key)
    if counts != expected_counts or len(rows) != 780:
        raise ValueError(f"Day 13 trial count changed: {counts}")


def create_design_lock(
    root: Path,
    run_id: str,
    output_root: Path,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    """Write and revalidate the design without running an estimator."""

    root = Path(root).resolve()
    if not git_status_clean(root):
        raise RuntimeError("Day 13 design lock requires a clean worktree")
    config = load_and_validate_day13_config(root)
    run_dir = Path(output_root).resolve() / str(run_id)
    design_dir = run_dir / "design"
    artifact_dir = root / DAY13_ARTIFACT_RELATIVE
    if (design_dir.exists() or artifact_dir.exists()) and not overwrite:
        raise FileExistsError("Day 13 design output already exists")
    if overwrite:
        import shutil
        for directory in (design_dir, artifact_dir):
            if directory.exists():
                shutil.rmtree(directory)
    design_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    exclusion = build_seed_exclusion_manifest(root)
    validate_seed_exclusion_manifest(exclusion)
    seed_lists = {
        role: {
            seed_type: list(exclusion[f"new_{role}_{seed_type}_seeds"])
            for seed_type in SEED_TYPES
        }
        for role in SEED_ROLES
    }
    plan = list(build_trial_plan(seed_lists))
    seed_records = list(exclusion["seed_records"])
    analysis_plan = {
        "schema_version": "stage2_failure_day13_analysis_plan_v1",
        "primary_statistic": "huber_cusum_max",
        "primary_statistic_role": "primary",
        "secondary_statistics": list(SECONDARY_STATISTICS),
        "secondary_statistic_role": "secondary_descriptive",
        "positive_population": "evaluation coherent active eligible rows by sweep",
        "negative_population": "evaluation matched severe clean eligible rows by sweep",
        "open_control_in_auroc": False,
        "gross_control_in_auroc_or_fpr": False,
        "threshold_source": "calibration clean eligible rows only",
        "threshold_quantile": 0.90,
        "threshold_quantile_rule": "nearest_rank",
        "threshold_comparison_operator": ">",
        "bootstrap_repetitions": 5000,
        "bootstrap_seed": 23131,
        "bootstrap_block": "geometry_seed",
        "descriptive_combined_only": True,
        "best_statistic_selected": False,
        "stage2_gate_decided": False,
        "stage3_threshold_created": False,
    }
    for directory in (artifact_dir, design_dir):
        write_json(directory / "seed_exclusion_manifest.json", exclusion)
        write_csv(directory / "seed_manifest.csv", seed_records)
        write_csv(directory / "trial_plan.csv", plan)
        write_json(directory / "analysis_plan.json", analysis_plan)

    code_paths = day13_analysis_code_paths(root)
    config_path = root / DAY13_CONFIG_RELATIVE
    day12_manifest = root / DAY12_RUN_RELATIVE / "run_manifest.json"
    day12_checkpoint = _git_rev_parse(root, f"{DAY12_CHECKPOINT}^{{}}")
    if not _git_is_ancestor(root, day12_checkpoint, "HEAD"):
        raise RuntimeError("Day 13 design must descend from the Day 12 v3 checkpoint")
    lock = {
        "schema_version": DAY13_DESIGN_SCHEMA_VERSION,
        "design_id": "stage2_failure_day13_new_seed_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_day12_v3_checkpoint": day12_checkpoint,
        "source_day12_v3_manifest_sha256": sha256_file(day12_manifest),
        "seed_generation_algorithm": exclusion["seed_generation_algorithm"],
        "seed_generation_labels": [row["label"] for row in seed_records],
        "seed_exclusion_sources": exclusion["source_paths"],
        "seed_exclusion_manifest_sha256": sha256_file(
            artifact_dir / "seed_exclusion_manifest.json"
        ),
        "seed_manifest_sha256": sha256_file(artifact_dir / "seed_manifest.csv"),
        "trial_plan_sha256": sha256_file(artifact_dir / "trial_plan.csv"),
        "analysis_plan_sha256": sha256_file(artifact_dir / "analysis_plan.json"),
        "calibration_seed_lists": seed_lists["calibration"],
        "evaluation_seed_lists": seed_lists["evaluation"],
        "calibration_evaluation_disjoint": True,
        "historical_seed_overlap_count": 0,
        "method_list": list(METHODS),
        "stress_list": list(STRESSES),
        "sweep_list": list(SWEEPS),
        "level_list": list(GEOMETRY_LEVELS + OBSERVATION_LEVELS + ("OC",)),
        "calibration_expected_trial_count": 260,
        "evaluation_expected_trial_count": 520,
        "primary_statistic": "huber_cusum_max",
        "secondary_statistics": list(SECONDARY_STATISTICS),
        "primary_score_eligibility_rule": (
            "stat_input_valid and window_ready and isfinite(huber_cusum_max)"
        ),
        "positive_population_rule": (
            "evaluation coherent_subhuber_slip stress_active eligible rows by sweep"
        ),
        "negative_population_rule": (
            "evaluation matched L3/L4 or O3/O4 clean eligible rows by sweep"
        ),
        "threshold_quantile": 0.90,
        "threshold_quantile_rule": "nearest_rank",
        "threshold_comparison_operator": ">",
        "bootstrap_repetitions": 5000,
        "bootstrap_seed": 23131,
        "bootstrap_block": "geometry_seed",
        "stage2_gate_not_decided": True,
        "stage3_threshold_not_created": True,
        "analysis_code_sha256": compute_bundle_hash(code_paths),
        "config_sha256": sha256_file(config_path),
        "git_commit_at_design": git_commit(root),
        "git_status_clean_at_design": True,
        "frozen_stress_config_sha256": sha256_file(root / "configs/update/stage2c_stress.yaml"),
        "frozen_coherent_stress": _frozen_stress(root, "coherent_subhuber_slip"),
        "frozen_gross_control": _frozen_stress(root, "gross_outlier_control"),
        "historical_artifact_hashes_at_design": {
            relative: compute_directory_hash(root / relative)
            for relative in (
                "artifacts/current/detector_stage2a",
                "artifacts/history/stage2b_column_scaling_no_go",
                "artifacts/current/weak_update_stage2c",
            )
        },
        "day11_cases_used": False,
        "reserved_test_namespace_consumed": False,
    }
    for directory in (artifact_dir, design_dir):
        write_json(directory / "design_lock.json", lock)
    validate_design_lock(root, artifact_dir / "design_lock.json")
    if (artifact_dir / "design_lock.json").read_bytes() != (design_dir / "design_lock.json").read_bytes():
        raise RuntimeError("Day 13 design lock copies differ")
    return {
        "result_dir": str(run_dir),
        "design_lock": str(artifact_dir / "design_lock.json"),
        "design_lock_sha256": sha256_file(artifact_dir / "design_lock.json"),
        "calibration_expected_trial_count": 260,
        "evaluation_expected_trial_count": 520,
        "estimator_run": False,
        "seed_exclusion_audit_pass": True,
        "config": config,
    }


def validate_design_lock(root: Path, path: Path) -> Mapping[str, Any]:
    root = Path(root).resolve()
    path = Path(path).resolve()
    lock = read_json(path)
    if lock.get("schema_version") != DAY13_DESIGN_SCHEMA_VERSION:
        raise ValueError("unexpected Day 13 design-lock schema")
    fixed = {
        "method_list": list(METHODS),
        "stress_list": list(STRESSES),
        "sweep_list": list(SWEEPS),
        "calibration_expected_trial_count": 260,
        "evaluation_expected_trial_count": 520,
        "primary_statistic": "huber_cusum_max",
        "secondary_statistics": list(SECONDARY_STATISTICS),
        "threshold_quantile": 0.90,
        "threshold_quantile_rule": "nearest_rank",
        "threshold_comparison_operator": ">",
        "bootstrap_repetitions": 5000,
        "bootstrap_seed": 23131,
        "bootstrap_block": "geometry_seed",
        "stage2_gate_not_decided": True,
        "stage3_threshold_not_created": True,
        "calibration_evaluation_disjoint": True,
        "historical_seed_overlap_count": 0,
        "day11_cases_used": False,
        "reserved_test_namespace_consumed": False,
    }
    for field, value in fixed.items():
        if lock.get(field) != value or type(lock.get(field)) is not type(value):
            raise ValueError(f"Day 13 design-lock field changed: {field}")
    directory = path.parent
    exclusion_path = directory / "seed_exclusion_manifest.json"
    seed_path = directory / "seed_manifest.csv"
    plan_path = directory / "trial_plan.csv"
    analysis_path = directory / "analysis_plan.json"
    for file_path in (exclusion_path, seed_path, plan_path, analysis_path):
        if not file_path.is_file():
            raise FileNotFoundError(f"Day 13 design file is missing: {file_path}")
    exclusion = read_json(exclusion_path)
    validate_seed_exclusion_manifest(exclusion)
    current_scan = scan_historical_seed_sources(root)
    for field in (
        "source_paths", "source_sha256", "historical_geometry_seeds",
        "historical_sensor_seeds", "historical_process_seeds", "parse_errors",
        "historical_source_parse_pass",
    ):
        if exclusion.get(field) != current_scan.get(field):
            raise ValueError(f"Day 13 historical seed source changed: {field}")
    expected_hashes = {
        "seed_exclusion_manifest_sha256": sha256_file(exclusion_path),
        "seed_manifest_sha256": sha256_file(seed_path),
        "trial_plan_sha256": sha256_file(plan_path),
        "analysis_plan_sha256": sha256_file(analysis_path),
    }
    for field, value in expected_hashes.items():
        if lock.get(field) != value:
            raise ValueError(f"Day 13 design-lock hash changed: {field}")
    seed_lists = {
        role: {seed_type: [int(v) for v in lock[f"{role}_seed_lists"][seed_type]] for seed_type in SEED_TYPES}
        for role in SEED_ROLES
    }
    expected_records = list(exclusion["seed_records"])
    actual_records = read_csv(seed_path)
    if len(actual_records) != len(expected_records):
        raise ValueError("Day 13 seed manifest row count changed")
    for actual, expected in zip(actual_records, expected_records):
        if {key: str(value) for key, value in expected.items()} != actual:
            raise ValueError("Day 13 seed manifest content changed")
    plan = [_normalize_trial_row(row) for row in read_csv(plan_path)]
    validate_trial_plan(plan, seed_lists)
    if plan != list(build_trial_plan(seed_lists)):
        raise ValueError("Day 13 trial plan is not deterministically reproducible")
    if lock.get("analysis_code_sha256") != compute_bundle_hash(day13_analysis_code_paths(root)):
        raise ValueError("Day 13 analysis code hash changed")
    if lock.get("config_sha256") != sha256_file(root / DAY13_CONFIG_RELATIVE):
        raise ValueError("Day 13 config hash changed")
    if lock.get("source_day12_v3_manifest_sha256") != sha256_file(
        root / DAY12_RUN_RELATIVE / "run_manifest.json"
    ):
        raise ValueError("Day 12 v3 manifest changed after design locking")
    return lock


def day13_analysis_code_paths(root: Path) -> Sequence[Path]:
    root = Path(root).resolve()
    relatives = (
        "src/eval/stage2_failure_day13_seeds.py",
        "src/eval/stage2_failure_day13_design.py",
        "src/eval/stage2_failure_day13_statistics.py",
        "src/eval/stage2_failure_day13_causal.py",
        "src/eval/stage2_failure_day13_schema.py",
        "src/eval/stage2_failure_day13.py",
        "scripts/38_run_stage2_failure_day13.py",
    )
    paths = [root / value for value in relatives]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Day 13 analysis code is incomplete: {missing}")
    return paths


def _normalize_trial_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    output = dict(row)
    for field in ("geometry_seed", "sensor_seed", "process_seed", "expected_frame_count"):
        output[field] = int(output[field])
    return output


def _frozen_stress(root: Path, name: str) -> Mapping[str, Any]:
    config = load_yaml(Path(root) / "configs/update/stage2c_stress.yaml")
    value = config.get("stress_regimes", {}).get(name)
    if not isinstance(value, dict):
        raise ValueError(f"frozen Stage 2C stress is missing: {name}")
    return value


def _git_rev_parse(root: Path, revision: str) -> str:
    import subprocess
    return subprocess.check_output(["git", "rev-parse", revision], cwd=str(root), text=True).strip()


def _git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    import subprocess
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=str(root), check=False,
    ).returncode == 0
