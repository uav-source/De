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
    return rows


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
