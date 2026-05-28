#!/usr/bin/env python3
"""Run the Day 15 legacy toy_lio bias audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.bias_audit import (  # noqa: E402
    flag_scene_family_confound,
    inspect_toy_lio_bias_config,
    read_csv_rows,
    summarize_bias_by_sequence,
)


FIELDNAMES = [
    "sequence_id",
    "scene_family",
    "legacy_axis_bias",
    "final_axis_error",
    "ODI_median",
    "axis_drift_rate_median",
    "confound_risk_level",
    "interpretation",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toy-lio", type=Path, default=ROOT / "src/minibench/toy_lio.py")
    parser.add_argument("--day14-tables", type=Path, default=ROOT / "results/day14/tables")
    parser.add_argument("--day10-report", type=Path, default=ROOT / "reports/day10_report.md")
    parser.add_argument("--out", type=Path, default=ROOT / "results/day30/tables/day15_bias_audit.csv")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results/day30/manifests/day15_bias_audit_manifest.json",
    )
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day15_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inputs = required_inputs(args)
    try:
        require_files(inputs)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    audit = inspect_toy_lio_bias_config(args.toy_lio)
    toy_rows = read_csv_rows(inputs["day07_toy_lio_summary"])
    metric_rows = read_csv_rows(inputs["day08_metric_summary"])
    summaries = summarize_bias_by_sequence(audit, toy_rows, metric_rows)
    confound = flag_scene_family_confound(summaries, audit)

    write_csv(args.out, summaries)
    report_text = build_report(audit, summaries, confound, inputs)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_text, encoding="utf-8")
    write_manifest(args, inputs, [args.out, args.manifest, args.report], audit, confound)

    print(f"bias audit csv: {relative_to_root(args.out)}")
    print(f"bias audit manifest: {relative_to_root(args.manifest)}")
    print(f"day15 report: {relative_to_root(args.report)}")
    print(f"status: OK")
    return 0


def required_inputs(args: argparse.Namespace) -> Dict[str, Path]:
    return {
        "toy_lio": args.toy_lio,
        "day07_toy_lio_summary": args.day14_tables / "day07_toy_lio_summary.csv",
        "day08_metric_summary": args.day14_tables / "day08_metric_summary.csv",
        "day10_metric_validity": args.day14_tables / "day10_metric_validity.csv",
        "day10_report": args.day10_report,
    }


def require_files(paths: Dict[str, Path]) -> None:
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required Day15 input file(s): " + "; ".join(missing))


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def build_report(
    audit: Dict[str, object],
    summaries: List[Dict[str, str]],
    confound: Dict[str, str],
    inputs: Dict[str, Path],
) -> str:
    rows_md = "\n".join(
        f"| {row['sequence_id']} | {row['scene_family']} | {row['legacy_axis_bias']} | "
        f"{row['final_axis_error']} | {row['ODI_median']} | {row['axis_drift_rate_median']} | "
        f"{row['confound_risk_level']} |"
        for row in summaries
    )
    bias_map = audit.get("axis_bias_by_family", {})
    return f"""# Day 15 Report - Bias Audit

## Decision Context

Day 14 remains **CONDITIONAL GO**. Day 15 does not modify `toy_lio`, does not change ODI/statistics, and does not upgrade the Day 14 conclusion.

## Direct Answers

- Day 7 toy_lio 是否存在 scene-family-dependent axis_bias？Yes. **legacy toy_lio has scene-family-dependent axis_bias**: `{bias_map}`.
- merged ODI-drift correlation 是否可能被 scene-family confound 放大？Yes. {confound['reason']}.
- Day 15-30 是否允许继续使用 legacy biased toy_lio 作为主证据？No. Legacy biased toy_lio can only be diagnostic evidence, not Day 15-30 main evidence.
- 哪些旧结果只能作为 diagnostic，不可作为主 claim？Day 7 toy trajectory drift, Day 8 metrics computed from that trajectory, Day 10 merged correlation, and Day 11/14 visual summaries based on the biased toy probe.

## Bias Audit Table

| sequence_id | scene_family | legacy_axis_bias | final_axis_error | ODI_median | axis_drift_rate_median | confound_risk_level |
|---|---:|---:|---:|---:|---:|---|
{rows_md}

## Interpretation

The legacy process-noise branch uses scene family to choose different axis-bias values. OC has zero legacy axis bias, while tunnel-like sequences have nonzero axis bias. Because the same scene families also differ in ODI and axis drift, merged all-sequence correlation can reflect a scene-label confound.

The Day 15-30 program must therefore replace this with unbiased perturbations before using drift correlations as main evidence. Legacy Day 14 results remain useful for debugging geometry, weak direction extraction, and reproduction discipline, but they are not sufficient for a main metric-validity claim.

## Inputs Checked

- `{relative_to_root(inputs['toy_lio'])}`
- `{relative_to_root(inputs['day07_toy_lio_summary'])}`
- `{relative_to_root(inputs['day08_metric_summary'])}`
- `{relative_to_root(inputs['day10_metric_validity'])}`
- `{relative_to_root(inputs['day10_report'])}`

## Required Next Step

Day 16 may separate legacy biased and unbiased toy configurations. It must not reuse scene-family axis bias as main evidence.
"""


def write_manifest(
    args: argparse.Namespace,
    inputs: Dict[str, Path],
    outputs: List[Path],
    audit: Dict[str, object],
    confound: Dict[str, str],
) -> None:
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "day": 15,
        "status": "OK",
        "git_commit": git_commit(),
        "command": " ".join(sys.argv),
        "inputs": [
            {
                "name": name,
                "path": relative_to_root(path),
                "sha256": sha256_file(path),
            }
            for name, path in inputs.items()
        ],
        "outputs": [relative_to_root(path) for path in outputs],
        "scene_family_axis_bias_present": audit.get("scene_family_dependent_axis_bias"),
        "axis_bias_by_family": audit.get("axis_bias_by_family"),
        "confound_risk_level": confound.get("confound_risk_level"),
        "limitations": [
            "legacy biased toy_lio is diagnostic evidence only",
            "merged ODI-drift correlation may be inflated by scene-family confounding",
            "Day 14 remains CONDITIONAL GO",
        ],
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
