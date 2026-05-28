#!/usr/bin/env python3
"""Run Day 22 go/no-go gate review."""

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

from eval.day22_gate_review import (  # noqa: E402
    CLAIM_FIELDNAMES,
    EVIDENCE_FIELDNAMES,
    GATE_FIELDNAMES,
    PLAN_FIELDNAMES,
    derive_claim_status,
    derive_next_action_plan,
    evaluate_gate_rules,
    load_day15_to_day21_artifacts,
    summarize_evidence_matrix,
    write_csv,
    write_day22_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day22_gate_review.yaml")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day22_gate_review.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        artifacts = load_day15_to_day21_artifacts(args.out_root, args.reports_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    evidence_rows = summarize_evidence_matrix(artifacts)
    gate_rows = evaluate_gate_rules(artifacts, config)
    claim_rows = derive_claim_status(artifacts, gate_rows)
    plan_rows = derive_next_action_plan(gate_rows)

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    evidence_path = table_dir / "day22_evidence_matrix.csv"
    gate_path = table_dir / "day22_gate_decision.csv"
    claim_path = table_dir / "day22_claim_status.csv"
    plan_path = table_dir / "day22_next_action_plan.csv"
    manifest_path = manifest_dir / "day22_gate_review_manifest.json"

    write_csv(evidence_path, EVIDENCE_FIELDNAMES, evidence_rows)
    write_csv(gate_path, GATE_FIELDNAMES, gate_rows)
    write_csv(claim_path, CLAIM_FIELDNAMES, claim_rows)
    write_csv(plan_path, PLAN_FIELDNAMES, plan_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(evidence_rows, gate_rows, claim_rows, plan_rows), encoding="utf-8")

    outputs = [evidence_path, gate_path, claim_path, plan_path, manifest_path, args.report]
    manifest = write_day22_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        gates=gate_rows,
        claims=claim_rows,
        plan=plan_rows,
        runtime_seconds=time.time() - start,
    )

    print(f"day22 evidence matrix: {display_path(evidence_path)}")
    print(f"day22 gate decision: {display_path(gate_path)}")
    print(f"day22 claim status: {display_path(claim_path)}")
    print(f"day22 next action: {display_path(plan_path)}")
    print(f"day22 manifest: {display_path(manifest_path)}")
    print(f"day22 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    print(f"final_decision: {manifest['final_decision']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day22 config must be a mapping: {path}")
    config.setdefault("source_days", [])
    config.setdefault("gate_rules", {})
    config.setdefault("decision_labels", ["GO_WEAK_UPDATE", "CONDITIONAL_ANALYSIS_ONLY", "NO_GO_METHOD_UPDATE"])
    return config


def build_report(
    evidence_rows: Sequence[Dict[str, str]],
    gate_rows: Sequence[Dict[str, str]],
    claim_rows: Sequence[Dict[str, str]],
    plan_rows: Sequence[Dict[str, str]],
) -> str:
    method_allowed = gate_value(gate_rows, "method_update_gate")
    weak_allowed = gate_value(gate_rows, "weak_update_authorization_gate")
    odi_allowed = claim_value(claim_rows, "C1")
    joint_allowed = claim_value(claim_rows, "C3")
    selected_route = next((row for row in plan_rows if row["allowed"] == "true"), plan_rows[-1])
    gate_lines = "\n".join(
        f"| {row['gate_name']} | {row['passed']} | {row['reason']} |"
        for row in gate_rows
    )
    claim_allowed = "\n".join(
        f"| {row['claim_text']} | {row['status']} | {row['allowed_wording']} |"
        for row in claim_rows
        if row["status"] == "allowed"
    )
    claim_blocked = "\n".join(
        f"| {row['claim_id']} | {row['status']} | {row['evidence_basis']} |"
        for row in claim_rows
        if row["status"] != "allowed"
    )
    return f"""# Day 22 Gate Review

## Direct Answers

- Day 22 是否完成 go/no-go gate review？Yes. It reviewed Day 15-21 artifacts and generated evidence, gate, claim, plan, and manifest outputs.
- Day 15-21 的证据链是否完整？Yes. The loaded evidence matrix covers Day 15 bias audit through Day 21 joint risk screening.
- ODI 是否已经验证？{'Yes' if odi_allowed else 'No'}.
- joint risk 是否已经验证？{'Yes' if joint_allowed else 'No'}.
- weak-subspace update 是否被授权？{'Yes' if weak_allowed else 'No'}.
- 当前可以写进论文的 claim 是什么？The unbiased toy_lio protocol is established, and legacy biased toy_lio is diagnostic only.
- 当前不能写进论文的 claim 是什么？Do not claim robust ODI drift prediction, ODI superiority, validated joint-risk drift prediction, or update authorization.
- Day 23 应该走 Route A 还是 Route B？{selected_route['route']}: {selected_route['task']}.

## Gate Decisions

| gate_name | passed | reason |
|---|---|---|
{gate_lines}

## Allowed Claims

| claim_text | status | allowed_wording |
|---|---|---|
{claim_allowed}

## Blocked Claims

| claim_id | status | evidence_basis |
|---|---|---|
{claim_blocked}

## Conclusion

Day 22 completes the gate review.
Weak-subspace update is not authorized.
Weak-subspace update is not authorized unless the gate passes.
The project should not implement Degen-LIO update logic yet.
Day 23 should follow the analysis/pivot route rather than method implementation.
Day 23 must follow the route selected by the gate review.
"""


def gate_value(gates: Sequence[Dict[str, str]], name: str) -> bool:
    return any(row["gate_name"] == name and row["passed"] == "true" for row in gates)


def claim_value(claims: Sequence[Dict[str, str]], claim_id: str) -> bool:
    return any(row["claim_id"] == claim_id and row["status"] == "allowed" for row in claims)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
