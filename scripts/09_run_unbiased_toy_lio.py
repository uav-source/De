#!/usr/bin/env python3
"""Run the Day 16 unbiased toy_lio protocol without touching Day 14 outputs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.metrics import (  # noqa: E402
    compute_axis_error,
    compute_cumulative_path_length,
    compute_sliding_window_drift_rate,
    load_axis_csv,
    load_tum_pose,
)
from minibench.toy_lio import (  # noqa: E402
    LEGACY_AXIS_BIAS_BY_FAMILY,
    load_toy_lio_config,
    resolve_axis_bias,
    run_toy_lio,
    save_pose_est_tum,
)


SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]
SUMMARY_FIELDS = [
    "sequence_id",
    "scene_family",
    "axis_bias_mode",
    "perturbation_profile",
    "legacy_axis_bias",
    "applied_axis_bias",
    "final_axis_error",
    "axis_drift_rate_median",
    "ODI_median",
    "AIS_median",
    "lambda_min_clamped_median",
    "condition_number_median",
    "is_unbiased_protocol",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/toy_lio/unbiased_day16.yaml")
    parser.add_argument("--detector-config", type=Path, default=ROOT / "configs/detector/odi_default.yaml")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/minibench")
    parser.add_argument("--day14-results", type=Path, default=ROOT / "results/day14")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day16_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_toy_lio_config(args.config)
    inputs = collect_inputs(args)
    missing = [f"{name}: {path}" for name, path in inputs.items() if not path.exists()]
    if missing:
        print("Missing required Day16 input file(s): " + "; ".join(missing), file=sys.stderr)
        return 2

    raw_out = args.out_root / "raw/unbiased_day16"
    table_out = args.out_root / "tables/day16_unbiased_toy_lio_summary.csv"
    manifest_out = args.out_root / "manifests/day16_unbiased_toy_lio_manifest.json"
    report_out = args.report
    raw_out.mkdir(parents=True, exist_ok=True)
    table_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    output_pose_files: List[Path] = []
    for sequence_id in SEQUENCES:
        sequence_dir = args.data_root / sequence_id
        result = run_toy_lio(sequence_dir, args.detector_config, config)
        pose_path = raw_out / f"{sequence_id}_pose_est_toy.tum"
        save_pose_est_tum(result["poses"], pose_path)
        output_pose_files.append(pose_path)
        rows.append(build_summary_row(sequence_id, sequence_dir, args.day14_results, result, config))

    write_summary(table_out, rows)
    unbiased_passed = all(row["axis_bias_mode"] == "none" and row["applied_axis_bias"] == "0" and row["is_unbiased_protocol"] == "true" for row in rows)
    legacy_preserved = legacy_behavior_preserved()
    status = "OK" if unbiased_passed and legacy_preserved else "FAILED"
    outputs = [table_out, manifest_out, report_out] + output_pose_files
    write_report(report_out, rows, config, unbiased_passed, legacy_preserved)
    write_manifest(
        manifest_out,
        args,
        config,
        inputs,
        outputs,
        status,
        legacy_preserved,
        unbiased_passed,
        time.time() - start,
    )

    print(f"unbiased toy_lio summary: {relative_to_root(table_out)}")
    print(f"unbiased toy_lio manifest: {relative_to_root(manifest_out)}")
    print(f"day16 report: {relative_to_root(report_out)}")
    print(f"status: {status}")
    return 0 if status == "OK" else 1


def collect_inputs(args: argparse.Namespace) -> Dict[str, Path]:
    inputs = {
        "toy_config": args.config,
        "detector_config": args.detector_config,
        "toy_lio": ROOT / "src/minibench/toy_lio.py",
        "day15_bias_audit": args.out_root / "tables/day15_bias_audit.csv",
        "day15_bias_manifest": args.out_root / "manifests/day15_bias_audit_manifest.json",
        "day10_metric_validity_per_sequence": args.day14_results / "tables/day10_metric_validity_per_sequence.csv",
        "day10_metric_validity_loso": args.day14_results / "tables/day10_metric_validity_loso.csv",
    }
    for sequence_id in SEQUENCES:
        seq_dir = args.data_root / sequence_id
        inputs[f"{sequence_id}_scene_metadata"] = seq_dir / "scene_metadata.json"
        inputs[f"{sequence_id}_gt"] = seq_dir / "gt.tum"
        inputs[f"{sequence_id}_axis"] = seq_dir / "axis.csv"
        inputs[f"{sequence_id}_observations"] = seq_dir / "observations.npz"
        inputs[f"{sequence_id}_odi"] = args.day14_results / "raw" / f"{sequence_id}_odi.csv"
    return inputs


def build_summary_row(sequence_id: str, sequence_dir: Path, day14_results: Path, result: Dict[str, object], config: Dict[str, object]) -> Dict[str, str]:
    scene_metadata = json.loads((sequence_dir / "scene_metadata.json").read_text(encoding="utf-8"))
    scene_family = str(scene_metadata["scene_family"])
    bias_metadata = result["bias_metadata"]
    est = result["poses"]
    gt = load_tum_pose(sequence_dir / "gt.tum")
    axis = load_axis_csv(sequence_dir / "axis.csv")
    axis_error = compute_axis_error(est, gt, axis)
    path_length = compute_cumulative_path_length(gt)
    windows = compute_sliding_window_drift_rate(axis_error, path_length, window_size=20, stride=5)
    axis_drift_rate_median = float(np.median(windows["drift_rate"])) if windows.shape[0] else 0.0
    spectral = summarize_spectral_metrics(day14_results / "raw" / f"{sequence_id}_odi.csv")
    return {
        "sequence_id": sequence_id,
        "scene_family": scene_family,
        "axis_bias_mode": str(config["axis_bias_mode"]),
        "perturbation_profile": str(config["perturbation_profile"]),
        "legacy_axis_bias": format_float(float(LEGACY_AXIS_BIAS_BY_FAMILY[scene_family])),
        "applied_axis_bias": format_float(float(bias_metadata["applied_axis_bias"])),
        "final_axis_error": format_float(float(result["summary"]["final_axis_error"])),
        "axis_drift_rate_median": format_float(axis_drift_rate_median),
        "ODI_median": format_float(spectral["ODI_median"]),
        "AIS_median": format_float(spectral["AIS_median"]),
        "lambda_min_clamped_median": format_float(spectral["lambda_min_clamped_median"]),
        "condition_number_median": format_float(spectral["condition_number_median"]),
        "is_unbiased_protocol": str(bool(bias_metadata["is_unbiased_protocol"])).lower(),
    }


def summarize_spectral_metrics(path: Path) -> Dict[str, float]:
    values = {"ODI": [], "AIS": [], "lambda_min_clamped": [], "condition_number": []}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for key in values:
                values[key].append(float(row[key]))
    return {
        "ODI_median": statistics.median(values["ODI"]),
        "AIS_median": statistics.median(values["AIS"]),
        "lambda_min_clamped_median": statistics.median(values["lambda_min_clamped"]),
        "condition_number_median": statistics.median(values["condition_number"]),
    }


def write_summary(path: Path, rows: List[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, rows: List[Dict[str, str]], config: Dict[str, object], unbiased_passed: bool, legacy_preserved: bool) -> None:
    row_lines = "\n".join(
        f"| {row['sequence_id']} | {row['scene_family']} | {row['legacy_axis_bias']} | "
        f"{row['applied_axis_bias']} | {row['final_axis_error']} | {row['is_unbiased_protocol']} |"
        for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# Day 16 Report - Unbiased toy_lio Protocol

## Direct Answers

- Day 16 是否修改了 legacy toy_lio 的默认复现行为？No. Default `run_toy_lio(...)` still uses `axis_bias_mode=legacy_scene_family`.
- legacy scene-family axis_bias 是否被保留为显式 legacy mode？Yes. `legacy_scene_family` preserves OC=0, CT=0.016, ST=0.022, RT=0.026.
- unbiased mode 中 applied_axis_bias 是否全部为 0？{'Yes' if unbiased_passed else 'No'}.
- Day 16 能否证明 ODI 有效？No. Day 16 only establishes the unbiased protocol and does not test metric validity.
- Day 16 结果是否可以替代 Day 14 legacy biased toy_lio 作为主证据？No. It is a protocol and smoke execution check; Day 17-22 must provide unbiased metric validity.

## Summary

| sequence_id | scene_family | legacy_axis_bias | applied_axis_bias | final_axis_error | is_unbiased_protocol |
|---|---|---:|---:|---:|---|
{row_lines}

## Protocol Status

- axis_bias_mode: `{config['axis_bias_mode']}`
- perturbation_profile: `{config['perturbation_profile']}`
- legacy_behavior_preserved: `{str(legacy_preserved).lower()}`
- unbiased_protocol_passed: `{str(unbiased_passed).lower()}`

## Conclusion

Day 16 establishes an unbiased toy_lio protocol, but does not yet validate ODI.
Metric validity must be tested in Day 17-22.
""",
        encoding="utf-8",
    )


def write_manifest(
    path: Path,
    args: argparse.Namespace,
    config: Dict[str, object],
    inputs: Dict[str, Path],
    outputs: List[Path],
    status: str,
    legacy_preserved: bool,
    unbiased_passed: bool,
    runtime_seconds: float,
) -> None:
    output_missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    manifest = {
        "status": status,
        "git_commit": git_commit(),
        "axis_bias_mode": config["axis_bias_mode"],
        "perturbation_profile": config["perturbation_profile"],
        "inputs": [relative_to_root(path) for path in inputs.values()],
        "outputs": [relative_to_root(path) for path in outputs],
        "legacy_behavior_preserved": bool(legacy_preserved),
        "unbiased_protocol_passed": bool(unbiased_passed),
        "missing_artifacts": output_missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "notes": "Day 16 establishes protocol only; metric validity remains blocked until Day 17-22.",
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def legacy_behavior_preserved() -> bool:
    return all(abs(resolve_axis_bias(family, {"axis_bias_mode": "legacy_scene_family"}) - value) < 1.0e-12 for family, value in LEGACY_AXIS_BIAS_BY_FAMILY.items())


def format_float(value: float) -> str:
    if abs(value) < 1.0e-12:
        return "0"
    return f"{value:.12g}"


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
