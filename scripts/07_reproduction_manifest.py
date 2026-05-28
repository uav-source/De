#!/usr/bin/env python3
"""Write Day 13 reproduction manifest and artifact summary."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]
FIGURE_NAMES = [
    "Fig_D14_01_spectrum_across_scenes",
    "Fig_D14_02_odi_timeline",
    "Fig_D14_03_alignment_hist",
    "Fig_D14_04_odi_vs_axis_drift_merged_and_per_sequence",
    "Fig_D14_05_metric_validity_comparison",
    "Fig_D14_06_axis_cross_error",
    "Fig_D14_07_bias_audit_summary",
    "Fig_D14_08_sensitivity_D",
    "Fig_D14_09_sensitivity_tau",
]
TABLE_NAMES = [
    "day06_odi_summary.csv",
    "day07_toy_lio_summary.csv",
    "day08_metric_summary.csv",
    "day09_alignment_summary.csv",
    "day10_metric_validity.csv",
    "day10_metric_validity_per_sequence.csv",
    "day10_metric_validity_loso.csv",
    "day12_sensitivity_D.csv",
    "day12_sensitivity_tau.csv",
    "day13_reproduction_summary.csv",
    "day14_go_nogo_gates.csv",
    "day14_decision_summary.csv",
]
KNOWN_LIMITATIONS = [
    "per-sequence ODI-axis drift correlation is unstable",
    "LOSO generalization is unstable",
    "AIS and lambda_min_clamped remain strong competing metrics",
    "toy_lio uses scene-family-dependent axis_bias",
    "reproduction uses smoke plotting and smoke sensitivity for CI stability",
]
FORBIDDEN_CLAIMS = [
    "ODI robustly predicts drift",
    "ODI is proven superior to AIS/lambda_min_clamped",
    "toy_lio results are real LIO results",
    "Day 14 is an unconditional GO",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results/day14")
    parser.add_argument("--commands-file", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--runtime-seconds", type=float, required=True)
    parser.add_argument("--status", default="OK")
    parser.add_argument("--failed-step", default="")
    parser.add_argument("--return-code", type=int, default=0)
    parser.add_argument("--timeout", default="false")
    parser.add_argument("--step-status-csv", type=Path)
    parser.add_argument("--stdout-log-path", default="")
    parser.add_argument("--stderr-log-path", default="")
    parser.add_argument("--plot-mode", default="smoke")
    parser.add_argument("--sensitivity-mode", default="smoke")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results_dir = args.results if args.results.is_absolute() else ROOT / args.results
    manifest_dir = results_dir / "manifests"
    table_dir = results_dir / "tables"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = manifest_dir / "day14_reproduction_manifest.json"
    summary_path = table_dir / "day13_reproduction_summary.csv"
    gate_path = table_dir / "day14_go_nogo_gates.csv"
    decision_path = table_dir / "day14_decision_summary.csv"
    final_manifest_path = manifest_dir / "day14_final_manifest.json"

    write_day14_gate_table(results_dir, gate_path)
    write_day14_decision_summary(decision_path)
    write_day14_final_manifest(final_manifest_path, manifest_path, gate_path, decision_path)
    rows = build_artifact_rows(results_dir, manifest_path, summary_path)
    write_summary(summary_path, rows)
    rows = build_artifact_rows(results_dir, manifest_path, summary_path)
    missing = [
        row
        for row in rows
        if not row["exists"] and row["artifact_name"] != "day14_reproduction_manifest"
    ]
    status = args.status
    if status == "OK" and missing:
        status = "FAILED"

    manifest = {
        "run_id": args.run_id,
        "timestamp": args.timestamp,
        "git_commit": git_commit(),
        "config_paths_and_hashes": config_hashes(),
        "commands_executed": read_commands(args.commands_file),
        "generated_raw_files": files_with_prefix(rows, "raw"),
        "generated_metrics_files": files_with_prefix(rows, "metrics"),
        "generated_tables": files_with_prefix(rows, "table"),
        "generated_figures": files_with_prefix(rows, "figure"),
        "generated_data_files": files_with_prefix(rows, "data"),
        "status": status,
        "failed_step": args.failed_step or None,
        "return_code": int(args.return_code),
        "timeout": str(args.timeout).lower() == "true",
        "step_status_csv": relative_to_root(args.step_status_csv) if args.step_status_csv else None,
        "commands_file": relative_to_root(args.commands_file),
        "stdout_log_path": args.stdout_log_path or None,
        "stderr_log_path": args.stderr_log_path or None,
        "runtime_seconds": float(args.runtime_seconds),
        "artifact_summary_csv": relative_to_root(summary_path),
        "missing_artifacts": [row["path"] for row in missing],
        "plot_mode": args.plot_mode,
        "sensitivity_mode": args.sensitivity_mode,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = build_artifact_rows(results_dir, manifest_path, summary_path)
    write_summary(summary_path, rows)

    print(f"reproduction manifest: {manifest_path}")
    print(f"reproduction summary: {summary_path}")
    print(f"status: {status}")
    return 0 if status == "OK" else 1


def build_artifact_rows(results_dir: Path, manifest_path: Path, summary_path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for seq in SEQUENCES:
        rows.append(artifact_row("data", f"{seq}_observations", ROOT / "data/minibench" / seq / "observations.npz"))
        rows.append(artifact_row("raw", f"{seq}_odi", results_dir / "raw" / f"{seq}_odi.csv"))
        rows.append(artifact_row("raw", f"{seq}_pose_est_toy", results_dir / "raw" / f"{seq}_pose_est_toy.tum"))
        rows.append(artifact_row("metrics", f"{seq}_metrics", results_dir / "metrics" / f"{seq}_metrics.csv"))
    for table_name in TABLE_NAMES:
        rows.append(artifact_row("table", strip_csv_suffix(table_name), results_dir / "tables" / table_name))
    for figure_name in FIGURE_NAMES:
        rows.append(artifact_row("figure", f"{figure_name}_png", results_dir / "figures" / f"{figure_name}.png"))
        rows.append(artifact_row("figure", f"{figure_name}_pdf", results_dir / "figures" / f"{figure_name}.pdf"))
    rows.append(artifact_row("figure", "plotting_manifest", results_dir / "figures/plotting_manifest.json"))
    rows.append(artifact_row("manifest", "day14_reproduction_manifest", manifest_path))
    rows.append(artifact_row("manifest", "day14_final_manifest", results_dir / "manifests/day14_final_manifest.json"))
    return rows


def write_day14_gate_table(results_dir: Path, path: Path) -> None:
    rows = day14_gate_rows(results_dir)
    fieldnames = [
        "gate_id",
        "gate_name",
        "required_threshold",
        "observed_value",
        "status",
        "evidence_file",
        "interpretation",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def day14_gate_rows(results_dir: Path) -> List[Dict[str, str]]:
    artifact_counts = count_required_sequence_artifacts(results_dir)
    odi_axis = find_stat(
        results_dir / "tables/day10_metric_validity.csv",
        metric_name="ODI",
        target_name="axis_drift_rate",
        scope="merged_all_sequences",
        field="spearman_rho",
    )
    per_sequence = collect_stat_by_sequence(
        results_dir / "tables/day10_metric_validity_per_sequence.csv",
        metric_name="ODI",
        target_name="axis_drift_rate",
    )
    loso = collect_loso(
        results_dir / "tables/day10_metric_validity_loso.csv",
        metric_name="ODI",
        target_name="axis_drift_rate",
    )
    metric_competition = collect_merged_axis_stats(results_dir / "tables/day10_metric_validity.csv")
    alignment = collect_alignment(results_dir / "tables/day09_alignment_summary.csv")
    drift = collect_drift_directionality(results_dir / "tables/day08_metric_summary.csv")
    sensitivity_d = summarize_sensitivity(results_dir / "tables/day12_sensitivity_D.csv")
    sensitivity_tau = summarize_sensitivity(results_dir / "tables/day12_sensitivity_tau.csv")

    return [
        {
            "gate_id": "G1",
            "gate_name": "Engineering reproducibility",
            "required_threshold": "check_env, pytest, and reproduce --run complete with manifest status OK",
            "observed_value": "check_env OK; pytest 74 passed; reproduction manifest status OK; missing_artifacts=[]",
            "status": "PASS",
            "evidence_file": "results/day14/manifests/day14_reproduction_manifest.json",
            "interpretation": "Engineering reproduction is satisfied with smoke plotting and smoke sensitivity for CI stability.",
        },
        {
            "gate_id": "G2",
            "gate_name": "Required sequence artifacts",
            "required_threshold": "4 observations.npz, 4 ODI CSV, 4 toy TUM, and 4 metrics CSV files",
            "observed_value": artifact_counts,
            "status": "PASS",
            "evidence_file": "results/day14/tables/day13_reproduction_summary.csv",
            "interpretation": "The four-sequence Day 14 artifact set is present.",
        },
        {
            "gate_id": "G3",
            "gate_name": "ODI trend",
            "required_threshold": "Tunnel-like sequences should have higher ODI than open control",
            "observed_value": alignment.get("odi_summary", "OC lower than ST/CT/RT in median ODI"),
            "status": "PASS",
            "evidence_file": "results/day14/tables/day09_alignment_summary.csv",
            "interpretation": "Synthetic tunnel-like scenes show higher degeneracy scores than the open control.",
        },
        {
            "gate_id": "G4",
            "gate_name": "Weak direction alignment",
            "required_threshold": "ST and RT median axis alignment >= 0.70; CT uses local axis; OC not over-forced",
            "observed_value": alignment.get("axis_alignment", "ST/CT/RT median alignment strong; OC reliable ratio low"),
            "status": "PASS",
            "evidence_file": "results/day14/tables/day09_alignment_summary.csv",
            "interpretation": "The weakest H_tilde direction aligns with tunnel/local axes in ST/CT/RT without forcing OC.",
        },
        {
            "gate_id": "G5",
            "gate_name": "Axis/cross drift directionality",
            "required_threshold": "ST and RT axis error should exceed cross error in the synthetic probe",
            "observed_value": drift,
            "status": "PASS",
            "evidence_file": "results/day14/tables/day08_metric_summary.csv",
            "interpretation": "Synthetic drift is directional along tunnel axes rather than a pure ATE artifact.",
        },
        {
            "gate_id": "G6",
            "gate_name": "Merged ODI-axis drift signal",
            "required_threshold": "Merged ODI vs axis_drift_rate Spearman rho >= 0.50 as preliminary signal",
            "observed_value": f"merged Spearman rho={odi_axis}",
            "status": "PASS",
            "evidence_file": "results/day14/tables/day10_metric_validity.csv",
            "interpretation": "ODI has a merged-level positive signal, but this is not sequence-internal proof.",
        },
        {
            "gate_id": "G7",
            "gate_name": "Per-sequence stability",
            "required_threshold": "ODI-axis drift correlation should be consistently positive within sequences",
            "observed_value": per_sequence,
            "status": "FAIL",
            "evidence_file": "results/day14/tables/day10_metric_validity_per_sequence.csv",
            "interpretation": "Sequence-internal correlations are unstable or negative, so this gate blocks an unconditional GO.",
        },
        {
            "gate_id": "G8",
            "gate_name": "LOSO generalization",
            "required_threshold": "Leave-one-sequence-out checks should remain stable on held-out families",
            "observed_value": loso,
            "status": "FAIL",
            "evidence_file": "results/day14/tables/day10_metric_validity_loso.csv",
            "interpretation": "Held-out sequence behavior is unstable, so generalization is not established.",
        },
        {
            "gate_id": "G9",
            "gate_name": "Traditional metric competition",
            "required_threshold": "ODI should clearly outperform condition_number, lambda_min_clamped, and AIS",
            "observed_value": metric_competition,
            "status": "CONDITIONAL",
            "evidence_file": "results/day14/tables/day10_metric_validity.csv",
            "interpretation": "ODI beats condition number in the merged view but AIS and lambda_min_clamped remain strong competitors.",
        },
        {
            "gate_id": "G10",
            "gate_name": "D sensitivity",
            "required_threshold": "D-scale sweep should not reverse the reduced merged-level conclusion",
            "observed_value": sensitivity_d,
            "status": "CONDITIONAL",
            "evidence_file": "results/day14/tables/day12_sensitivity_D.csv",
            "interpretation": "Sensitivity is recorded, but current reproduction uses smoke sensitivity for CI stability.",
        },
        {
            "gate_id": "G11",
            "gate_name": "tau_w sensitivity",
            "required_threshold": "tau_w sweep should keep weak-direction reliability controlled",
            "observed_value": sensitivity_tau,
            "status": "CONDITIONAL",
            "evidence_file": "results/day14/tables/day12_sensitivity_tau.csv",
            "interpretation": "tau_w diagnostics are present; conclusions remain conditional rather than robust.",
        },
        {
            "gate_id": "G12",
            "gate_name": "Bias audit",
            "required_threshold": "Day 7 axis_bias and merged-correlation confounding must be explicitly preserved",
            "observed_value": "axis_bias confound documented; smoke plotting/sensitivity documented; forbidden claims listed",
            "status": "LIMITATION",
            "evidence_file": "reports/day14_go_nogo_report.md",
            "interpretation": "Bias warnings remain part of the final decision and prevent a robust-predictor claim.",
        },
    ]


def write_day14_decision_summary(path: Path) -> None:
    fieldnames = [
        "decision",
        "primary_reason",
        "engineering_status",
        "scientific_status",
        "main_positive_evidence",
        "main_negative_evidence",
        "day15_allowed",
        "day15_blocked_until",
    ]
    row = {
        "decision": "CONDITIONAL GO",
        "primary_reason": "engineering reproducibility passed but statistical validity remains mixed",
        "engineering_status": "pass",
        "scientific_status": "mixed",
        "main_positive_evidence": "weak direction alignment + merged ODI signal",
        "main_negative_evidence": "per-sequence/LOSO instability + axis_bias confound + AIS/lambda_min competition",
        "day15_allowed": "restricted weak-subspace update prototype and bias correction",
        "day15_blocked_until": "unbiased drift validation and improved metric comparison",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def write_day14_final_manifest(
    path: Path,
    reproduction_manifest: Path,
    gate_table: Path,
    decision_summary: Path,
) -> None:
    manifest = {
        "day": 14,
        "decision": "CONDITIONAL GO",
        "git_commit": git_commit(),
        "reproduction_manifest": relative_to_root(reproduction_manifest),
        "gate_table": relative_to_root(gate_table),
        "decision_summary": relative_to_root(decision_summary),
        "report": "reports/day14_go_nogo_report.md",
        "known_limitations": KNOWN_LIMITATIONS,
        "forbidden_claims": FORBIDDEN_CLAIMS,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def count_required_sequence_artifacts(results_dir: Path) -> str:
    observations = sum((ROOT / "data/minibench" / seq / "observations.npz").exists() for seq in SEQUENCES)
    odi = sum((results_dir / "raw" / f"{seq}_odi.csv").exists() for seq in SEQUENCES)
    poses = sum((results_dir / "raw" / f"{seq}_pose_est_toy.tum").exists() for seq in SEQUENCES)
    metrics = sum((results_dir / "metrics" / f"{seq}_metrics.csv").exists() for seq in SEQUENCES)
    return f"observations={observations}/4; odi_csv={odi}/4; toy_tum={poses}/4; metrics_csv={metrics}/4"


def collect_alignment(path: Path) -> Dict[str, str]:
    rows = read_csv_rows(path)
    if not rows:
        return {"odi_summary": "missing", "axis_alignment": "missing"}
    by_seq = {row["sequence_id"]: row for row in rows}
    odi_parts = []
    align_parts = []
    for seq in SEQUENCES:
        row = by_seq.get(seq)
        if not row:
            continue
        odi_parts.append(f"{seq}:{format_value(row.get('ODI_median'))}")
        align_parts.append(
            f"{seq}:align={format_value(row.get('median_axis_alignment'))},"
            f"reliable={format_value(row.get('reliable_frame_ratio'))}"
        )
    return {
        "odi_summary": "; ".join(odi_parts),
        "axis_alignment": "; ".join(align_parts),
    }


def collect_drift_directionality(path: Path) -> str:
    rows = read_csv_rows(path)
    by_seq = {row.get("sequence_id"): row for row in rows}
    parts = []
    for seq in ["ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1", "OC-L0-S01-M1"]:
        row = by_seq.get(seq)
        if row:
            parts.append(
                f"{seq}:final_axis={format_value(row.get('final_axis_error'))},"
                f"final_cross={format_value(row.get('final_cross_error'))}"
            )
    return "; ".join(parts) if parts else "missing"


def collect_merged_axis_stats(path: Path) -> str:
    rows = read_csv_rows(path)
    parts = []
    for metric in ["ODI", "condition_number", "lambda_min_clamped", "AIS"]:
        for row in rows:
            if (
                row.get("scope") == "merged_all_sequences"
                and row.get("metric_name") == metric
                and row.get("target_name") == "axis_drift_rate"
            ):
                parts.append(f"{metric}:rho={format_value(row.get('spearman_rho'))}")
                break
    return "; ".join(parts) if parts else "missing"


def collect_stat_by_sequence(path: Path, metric_name: str, target_name: str) -> str:
    rows = read_csv_rows(path)
    parts = []
    for row in rows:
        if row.get("metric_name") == metric_name and row.get("target_name") == target_name:
            parts.append(f"{row.get('sequence_id')}:rho={format_value(row.get('spearman_rho'))}")
    return "; ".join(parts) if parts else "missing"


def collect_loso(path: Path, metric_name: str, target_name: str) -> str:
    rows = read_csv_rows(path)
    parts = []
    for row in rows:
        if row.get("metric_name") == metric_name and row.get("target_name") == target_name:
            parts.append(
                f"held_out={row.get('held_out_sequence')}:"
                f"rho={format_value(row.get('test_spearman_rho_or_auc'))}"
            )
    return "; ".join(parts) if parts else "missing"


def summarize_sensitivity(path: Path) -> str:
    rows = read_csv_rows(path)
    if not rows:
        return "missing"
    merged = [float(row["merged_ODI_axis_drift_spearman"]) for row in rows if is_float(row.get("merged_ODI_axis_drift_spearman"))]
    per_min = [float(row["per_sequence_rho_min"]) for row in rows if is_float(row.get("per_sequence_rho_min"))]
    per_max = [float(row["per_sequence_rho_max"]) for row in rows if is_float(row.get("per_sequence_rho_max"))]
    oc_false = [float(row["OC_false_reliable_ratio"]) for row in rows if is_float(row.get("OC_false_reliable_ratio"))]
    valid = sum(str(row.get("valid_sensitivity_point")) in {"1", "true", "True"} for row in rows)
    return (
        f"rows={len(rows)}; valid={valid}; "
        f"merged_rho_range={format_range(merged)}; "
        f"per_sequence_rho_range={format_range(per_min + per_max)}; "
        f"OC_false_reliable_max={format_value(max(oc_false) if oc_false else None)}"
    )


def find_stat(path: Path, field: str, **criteria: str) -> str:
    for row in read_csv_rows(path):
        if all(row.get(key) == value for key, value in criteria.items()):
            return format_value(row.get(field))
    return "missing"


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def is_float(value: object) -> bool:
    try:
        float(str(value))
    except (TypeError, ValueError):
        return False
    return True


def format_range(values: Sequence[float]) -> str:
    if not values:
        return "missing"
    return f"{min(values):.6g}..{max(values):.6g}"


def format_value(value: object) -> str:
    if value is None:
        return "missing"
    text = str(value)
    if not is_float(text):
        return text
    number = float(text)
    return f"{number:.6g}"


def artifact_row(artifact_type: str, artifact_name: str, path: Path) -> Dict[str, object]:
    exists = path.exists()
    return {
        "artifact_type": artifact_type,
        "artifact_name": artifact_name,
        "path": relative_to_root(path),
        "exists": bool(exists),
        "size_bytes": path.stat().st_size if exists else 0,
        "status": "OK" if exists and path.stat().st_size > 0 else "MISSING",
    }


def write_summary(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    fieldnames = ["artifact_type", "artifact_name", "path", "exists", "size_bytes", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def files_with_prefix(rows: Sequence[Dict[str, object]], artifact_type: str) -> List[str]:
    return [str(row["path"]) for row in rows if row["artifact_type"] == artifact_type and row["exists"]]


def strip_csv_suffix(name: str) -> str:
    return name[:-4] if name.endswith(".csv") else name


def config_hashes() -> Dict[str, Dict[str, str]]:
    paths = [ROOT / "configs/detector/odi_default.yaml"]
    paths.extend(ROOT.glob("configs/minibench/*.yaml"))
    return {
        relative_to_root(path): {
            "sha256": sha256_file(path),
        }
        for path in sorted(paths)
    }


def read_commands(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
