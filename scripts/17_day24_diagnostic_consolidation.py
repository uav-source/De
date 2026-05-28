#!/usr/bin/env python3
"""Run Day 24 diagnostic benchmark consolidation."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.day24_diagnostic_consolidation import (  # noqa: E402
    ARTIFACT_FIELDNAMES,
    CHECKLIST_FIELDNAMES,
    CLAIM_FIELDNAMES,
    PROTOCOL_FIELDNAMES,
    RECOMMENDATION_FIELDNAMES,
    RISK_FIELDNAMES,
    build_artifact_inventory,
    build_benchmark_protocol_table,
    build_paper_claim_map,
    build_release_checklist,
    build_reviewer_risk_register,
    derive_day25_recommendation,
    load_day14_to_day23_artifacts,
    write_csv,
    write_day24_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day24_diagnostic_consolidation.yaml")
    parser.add_argument("--day14-root", type=Path, default=ROOT / "results/day14")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day24_diagnostic_consolidation_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        artifacts = load_day14_to_day23_artifacts(args.day14_root, args.out_root, args.reports_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    inventory = build_artifact_inventory(artifacts)
    protocol = build_benchmark_protocol_table(artifacts)
    claims = build_paper_claim_map(artifacts)
    risks = build_reviewer_risk_register(artifacts)
    checklist = build_release_checklist(artifacts)
    recommendation = derive_day25_recommendation(artifacts)

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    inventory_path = table_dir / "day24_artifact_inventory.csv"
    protocol_path = table_dir / "day24_benchmark_protocol.csv"
    claim_path = table_dir / "day24_paper_claim_map.csv"
    risk_path = table_dir / "day24_reviewer_risk_register.csv"
    checklist_path = table_dir / "day24_release_checklist.csv"
    recommendation_path = table_dir / "day24_day25_recommendation.csv"
    manifest_path = manifest_dir / "day24_diagnostic_consolidation_manifest.json"

    write_csv(inventory_path, ARTIFACT_FIELDNAMES, inventory)
    write_csv(protocol_path, PROTOCOL_FIELDNAMES, protocol)
    write_csv(claim_path, CLAIM_FIELDNAMES, claims)
    write_csv(risk_path, RISK_FIELDNAMES, risks)
    write_csv(checklist_path, CHECKLIST_FIELDNAMES, checklist)
    write_csv(recommendation_path, RECOMMENDATION_FIELDNAMES, recommendation)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(inventory, claims, risks, checklist, recommendation), encoding="utf-8")

    outputs = [
        inventory_path,
        protocol_path,
        claim_path,
        risk_path,
        checklist_path,
        recommendation_path,
        manifest_path,
        args.report,
    ]
    manifest = write_day24_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        inventory=inventory,
        protocol=protocol,
        claims=claims,
        risks=risks,
        checklist=checklist,
        recommendation=recommendation,
        artifacts=artifacts,
        runtime_seconds=time.time() - start,
    )

    print(f"day24 artifact inventory: {display_path(inventory_path)}")
    print(f"day24 benchmark protocol: {display_path(protocol_path)}")
    print(f"day24 paper claim map: {display_path(claim_path)}")
    print(f"day24 reviewer risk register: {display_path(risk_path)}")
    print(f"day24 release checklist: {display_path(checklist_path)}")
    print(f"day24 recommendation: {display_path(recommendation_path)}")
    print(f"day24 manifest: {display_path(manifest_path)}")
    print(f"day24 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    print(f"recommended_day25_route: {manifest['recommended_day25_route']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day24 config must be a mapping: {path}")
    config.setdefault("route", "diagnostic_benchmark_consolidation")
    return config


def build_report(
    inventory: Sequence[Dict[str, str]],
    claims: Sequence[Dict[str, str]],
    risks: Sequence[Dict[str, str]],
    checklist: Sequence[Dict[str, str]],
    recommendation: Sequence[Dict[str, str]],
) -> str:
    allowed = [row["claim_id"] for row in claims if row["claim_status"] in {"allowed", "conditional", "diagnostic_only"}]
    forbidden = [row["claim_id"] for row in claims if row["claim_status"] == "forbidden"]
    top_risks = [row for row in risks if row["priority"] == "high"][:5]
    selected = [row for row in recommendation if row["allowed"] == "true"]
    selected_text = "; ".join(f"{row['recommended_route']}: {row['task']}" for row in selected)
    risk_lines = "\n".join(
        f"| {row['risk_id']} | {row['reviewer_attack']} | {row['severity']} | {row['mitigation_plan']} |"
        for row in top_risks
    )
    checklist_blockers = [row["check_id"] for row in checklist if row["blocking"] == "true" and row["status"] != "pass"]
    return f"""# Day 24 Diagnostic Benchmark Consolidation Report

## Direct Answers

- Day 24 是否完成 diagnostic benchmark consolidation？Yes. It consolidates {len(inventory)} tracked artifacts, claim boundaries, reviewer risks, release checks, and Day 25 route options.
- 当前 benchmark 能支撑什么论文 claim？Allowed or scoped claim IDs: `{', '.join(allowed)}`. These cover synthetic diagnostic geometry, unbiased protocol establishment, reproducibility with limits, and negative metric-validity evidence.
- 当前 benchmark 不能支撑什么论文 claim？Forbidden claim IDs: `{', '.join(forbidden)}`. These block robust drift-prediction, metric superiority, joint-risk prediction, and estimator-update readiness claims.
- 当前最大 reviewer attack 是什么？The largest attacks are synthetic-only scope, toy_lio not being real LIO, failed controlled metric validity, failed joint-risk gate, and absence of estimator update.
- 为什么 No-Go method update 仍然可以形成有价值的诊断型论文路线？Because the No-Go preserves evidence integrity and turns unsupported method claims into a reproducible benchmark, bias-audit, and failure-analysis contribution.
- 是否允许进入 weak-subspace update？No.
- Day 25 应该走 paper outline / figure-table plan，还是 metric redesign prototype review？Selected options: {selected_text}.

## Reviewer Risk Register Snapshot

| risk_id | reviewer_attack | severity | mitigation_plan |
|---|---|---|---|
{risk_lines}

## Release Readiness

Blocking release checks not yet passed: `{', '.join(checklist_blockers) if checklist_blockers else 'none'}`.

## Conclusion

Day 24 consolidates the project as a diagnostic benchmark / failure-analysis route.
The project still should not implement weak-subspace update.
The current evidence supports a reproducible diagnostic package with explicit claim boundaries, not a validated Degen-LIO estimator method.
Day 25 should proceed with either a paper outline / figure-table plan or a metric-redesign review, not method implementation.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
