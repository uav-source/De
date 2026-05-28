"""Day 22 go/no-go gate review over Day 15-21 evidence."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

EVIDENCE_FIELDNAMES = [
    "day",
    "source_file",
    "evidence_item",
    "evidence_type",
    "status",
    "key_metric",
    "observed_value",
    "interpretation",
    "claim_allowed",
]

GATE_FIELDNAMES = [
    "gate_name",
    "requirement",
    "observed",
    "passed",
    "decision_impact",
    "reason",
]

CLAIM_FIELDNAMES = [
    "claim_id",
    "claim_text",
    "status",
    "allowed_wording",
    "forbidden_wording",
    "evidence_basis",
]

PLAN_FIELDNAMES = [
    "next_day",
    "route",
    "task",
    "allowed",
    "reason",
]


def load_day15_to_day21_artifacts(day30_root: Path, reports_root: Path) -> Dict[str, Any]:
    """Load required reports, tables, and manifests from Day 15-21."""

    paths = {
        "day15_bias_audit": day30_root / "tables/day15_bias_audit.csv",
        "day15_manifest": day30_root / "manifests/day15_bias_audit_manifest.json",
        "day15_report": reports_root / "day15_report.md",
        "day16_summary": day30_root / "tables/day16_unbiased_toy_lio_summary.csv",
        "day16_manifest": day30_root / "manifests/day16_unbiased_toy_lio_manifest.json",
        "day16_report": reports_root / "day16_report.md",
        "day17_trials": day30_root / "tables/day17_unbiased_probe_trials.csv",
        "day17_manifest": day30_root / "manifests/day17_unbiased_probe_manifest.json",
        "day17_report": reports_root / "day17_report.md",
        "day18_windows": day30_root / "tables/day18_window_metrics.csv",
        "day18_manifest": day30_root / "manifests/day18_within_sequence_manifest.json",
        "day18_report": reports_root / "day18_report.md",
        "day19_pass_fail": day30_root / "tables/day19_metric_pass_fail_summary.csv",
        "day19_manifest": day30_root / "manifests/day19_grouped_loso_manifest.json",
        "day19_report": reports_root / "day19_report.md",
        "day20_incremental": day30_root / "tables/day20_incremental_validity_summary.csv",
        "day20_manifest": day30_root / "manifests/day20_controlled_partial_manifest.json",
        "day20_report": reports_root / "day20_report.md",
        "day21_comparison": day30_root / "tables/day21_joint_risk_comparison.csv",
        "day21_manifest": day30_root / "manifests/day21_joint_risk_manifest.json",
        "day21_report": reports_root / "day21_report.md",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day22 input file(s): "
            + "; ".join(missing)
            + ". Run Day 15-21 scripts before Day 22 gate review."
        )
    artifacts: Dict[str, Any] = {"paths": paths, "input_paths": list(paths.values())}
    for key, path in paths.items():
        if path.suffix == ".json":
            artifacts[key] = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".csv":
            artifacts[key] = read_csv_rows(path)
        else:
            artifacts[key] = path.read_text(encoding="utf-8")
    return artifacts


def summarize_evidence_matrix(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Create one evidence row for each major Day 15-21 finding."""

    day15_high = count_rows(artifacts["day15_bias_audit"], "confound_risk_level", {"HIGH", "MEDIUM"})
    day16_unbiased = all(
        row.get("axis_bias_mode") == "none"
        and abs(to_float(row.get("applied_axis_bias"))) <= 1.0e-12
        for row in artifacts["day16_summary"]
    )
    day17_trials = len(artifacts["day17_trials"])
    day18_rows = len(artifacts["day18_windows"])
    day19_odi = find_row(artifacts["day19_pass_fail"], "metric_name", "ODI_median", "target_name", "axis_drift_rate")
    day20_odi = find_row(artifacts["day20_incremental"], "metric_name", "ODI_median", "target_name", "axis_drift_rate")
    day21_best = best_day21_row(artifacts["day21_comparison"])
    weak_auth = bool(artifacts["day21_manifest"].get("weak_update_authorized", False))
    return [
        evidence_row(
            "15",
            artifacts["paths"]["day15_bias_audit"],
            "scene-family axis_bias audit",
            "bias_audit",
            "confirmed",
            "confound_risk_sequences",
            str(day15_high),
            "legacy toy_lio bias is diagnostic-only evidence and cannot support main claims",
            "true",
        ),
        evidence_row(
            "16",
            artifacts["paths"]["day16_summary"],
            "unbiased toy_lio protocol",
            "protocol",
            "validated" if day16_unbiased else "failed",
            "applied_axis_bias",
            "all_zero" if day16_unbiased else "nonzero_found",
            "axis_bias_mode=none keeps all applied_axis_bias values at zero",
            str(day16_unbiased).lower(),
        ),
        evidence_row(
            "17",
            artifacts["paths"]["day17_trials"],
            "unbiased multi-trial probe",
            "exploratory_probe",
            "exploratory",
            "trial_rows",
            str(day17_trials),
            "multi-trial data exist but do not validate metric claims",
            "diagnostic_only",
        ),
        evidence_row(
            "18",
            artifacts["paths"]["day18_windows"],
            "window-level within-sequence validation",
            "window_validation",
            "completed" if artifacts["day18_manifest"].get("status") == "OK" else "failed",
            "window_rows",
            str(day18_rows),
            "within-sequence correlations are available with undefined cases preserved",
            str(artifacts["day18_manifest"].get("status") == "OK").lower(),
        ),
        evidence_row(
            "19",
            artifacts["paths"]["day19_pass_fail"],
            "grouped / LOSO validation",
            "grouped_loso",
            str(day19_odi.get("final_day19_status", "missing")),
            "ODI_axis_drift",
            day19_odi.get("reason", "missing"),
            "ODI remained exploratory under grouped / LOSO screening",
            "false",
        ),
        evidence_row(
            "20",
            artifacts["paths"]["day20_incremental"],
            "controlled / partial validity",
            "controlled_partial",
            str(day20_odi.get("final_day20_status", "missing")),
            "ODI_axis_drift",
            day20_odi.get("reason", "missing"),
            "ODI did not pass controlled incremental validity",
            "false",
        ),
        evidence_row(
            "21",
            artifacts["paths"]["day21_comparison"],
            "joint risk feature analysis",
            "joint_risk",
            str(day21_best.get("final_day21_status", "missing")),
            str(day21_best.get("feature_name", "none")),
            str(day21_best.get("reason", "missing")),
            "all joint risk features remain exploratory and method update is not authorized",
            str(weak_auth).lower(),
        ),
    ]


def evaluate_gate_rules(artifacts: Mapping[str, Any], config: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Evaluate formal Day 22 go/no-go gate rules."""

    rules = dict(config.get("gate_rules", {}))
    day16_unbiased = all(
        row.get("axis_bias_mode") == "none"
        and abs(to_float(row.get("applied_axis_bias"))) <= 1.0e-12
        for row in artifacts["day16_summary"]
    )
    day18_ok = artifacts["day18_manifest"].get("status") == "OK" and len(artifacts["day18_windows"]) > 0
    day19_ok = artifacts["day19_manifest"].get("status") == "OK"
    day20_odi = find_row(artifacts["day20_incremental"], "metric_name", "ODI_median", "target_name", "axis_drift_rate")
    odi_controlled = day20_odi.get("final_day20_status") == "candidate_supported"
    joint_candidate = any(row.get("final_day21_status") == "candidate_supported" for row in artifacts["day21_comparison"])
    weak_update_authorized = bool(artifacts["day21_manifest"].get("weak_update_authorized", False))
    method_update = bool(joint_candidate and weak_update_authorized)
    gates = [
        gate_row(
            "unbiased_protocol_gate",
            "Day16 axis_bias_mode=none and applied_axis_bias all zero",
            str(day16_unbiased),
            day16_unbiased if rules.get("require_unbiased_protocol", True) else True,
            "blocks biased protocol claims if false",
            "unbiased protocol established" if day16_unbiased else "unbiased protocol failed",
        ),
        gate_row(
            "within_sequence_validation_gate",
            "Day18 window validation completed",
            str(day18_ok),
            day18_ok if rules.get("require_day18_window_validation", True) else True,
            "blocks Day19+ inference if false",
            "Day18 manifest OK with nonempty windows" if day18_ok else "Day18 validation missing or failed",
        ),
        gate_row(
            "grouped_loso_gate",
            "Day19 grouped / LOSO completed",
            str(day19_ok),
            day19_ok if rules.get("require_day19_grouped_loso", True) else True,
            "blocks generalization claims if false",
            "Day19 manifest OK" if day19_ok else "Day19 missing or failed",
        ),
        gate_row(
            "odi_controlled_validity_gate",
            "ODI candidate_supported in Day20 controlled validity",
            day20_odi.get("final_day20_status", "missing"),
            odi_controlled,
            "blocks single-ODI validity claims",
            day20_odi.get("reason", "missing"),
        ),
        gate_row(
            "joint_risk_candidate_gate",
            "At least one Day21 joint risk candidate_supported",
            str(joint_candidate),
            joint_candidate if rules.get("require_day21_joint_risk_candidate_for_method", True) else True,
            "blocks method update if false",
            "joint risk candidate exists" if joint_candidate else "no Day21 joint risk candidate passed",
        ),
        gate_row(
            "weak_update_authorization_gate",
            "Day21 manifest weak_update_authorized true",
            str(weak_update_authorized),
            weak_update_authorized if rules.get("require_weak_update_authorized_for_method", True) else True,
            "directly controls method update authorization",
            "Day21 authorized weak update" if weak_update_authorized else "Day21 did not authorize weak update",
        ),
        gate_row(
            "method_update_gate",
            "joint_risk_candidate_gate and weak_update_authorization_gate pass",
            str(method_update),
            method_update,
            "final method update go/no-go",
            "method update authorized" if method_update else "method update blocked by Day22 gate",
        ),
    ]
    return gates


def derive_claim_status(artifacts: Mapping[str, Any], gates: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    """Return allowed/forbidden claim wording from gate outcomes."""

    method_allowed = gate_passed(gates, "method_update_gate")
    weak_allowed = gate_passed(gates, "weak_update_authorization_gate")
    joint_candidate = gate_passed(gates, "joint_risk_candidate_gate")
    unbiased_allowed = gate_passed(gates, "unbiased_protocol_gate")
    day20_odi = find_row(artifacts["day20_incremental"], "metric_name", "ODI_median", "target_name", "axis_drift_rate")
    odi_validated = day20_odi.get("final_day20_status") == "candidate_supported"
    return [
        claim_row(
            "C1",
            "ODI robustly predicts drift",
            "allowed" if odi_validated else "forbidden",
            "ODI remains exploratory under current synthetic validation" if not odi_validated else "ODI has controlled candidate support in this limited probe",
            "Do not state ODI robustly predicts drift unless controlled and grouped gates pass",
            "Day20 ODI status: " + day20_odi.get("final_day20_status", "missing"),
        ),
        claim_row(
            "C2",
            "ODI is superior to AIS/lambda_min",
            "forbidden",
            "ODI is one exploratory metric among AIS, lambda_min_clamped, and condition_number",
            "Do not claim ODI superiority over AIS/lambda_min_clamped",
            "Day19/20 baseline competition remains unresolved",
        ),
        claim_row(
            "C3",
            "joint risk predicts drift",
            "allowed" if joint_candidate else "forbidden",
            "joint risk features are exploratory diagnostics" if not joint_candidate else "a joint-risk candidate passed screening and awaits gate review",
            "Do not present joint risk as validated drift prediction without Day21 candidate support",
            "Day21 candidate gate: " + str(joint_candidate),
        ),
        claim_row(
            "C4",
            "unbiased toy_lio protocol is established",
            "allowed" if unbiased_allowed else "forbidden",
            "unbiased toy_lio protocol is established for synthetic diagnostic probes",
            "Do not call unbiased toy_lio a real LIO system",
            "Day16 applied_axis_bias all zero: " + str(unbiased_allowed),
        ),
        claim_row(
            "C5",
            "legacy toy_lio is diagnostic only",
            "allowed",
            "legacy biased toy_lio is diagnostic evidence only",
            "Do not use legacy biased toy_lio as main evidence",
            "Day15 bias audit confirmed scene-family-dependent axis_bias",
        ),
        claim_row(
            "C6",
            "weak-subspace update is authorized",
            "allowed" if method_allowed and weak_allowed else "forbidden",
            "weak-subspace update is not authorized by Day22 gate" if not method_allowed else "weak-subspace update may enter design review only",
            "Do not implement weak-subspace update before gate authorization",
            "method_update_gate=" + str(method_allowed),
        ),
    ]


def derive_next_action_plan(gates: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    """Choose Route A or B from the method-update gate."""

    method_allowed = gate_passed(gates, "method_update_gate")
    return [
        {
            "next_day": "Day 23",
            "route": "Route A",
            "task": "weak-subspace update design review",
            "allowed": str(method_allowed).lower(),
            "reason": "allowed only if method_update_gate passes",
        },
        {
            "next_day": "Day 23",
            "route": "Route B",
            "task": "metric/risk redesign or diagnostic benchmark consolidation",
            "allowed": str(not method_allowed).lower(),
            "reason": "selected because method_update_gate is false" if not method_allowed else "not selected because method_update_gate passed",
        },
    ]


def write_day22_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    gates: Sequence[Mapping[str, str]],
    claims: Sequence[Mapping[str, str]],
    plan: Sequence[Mapping[str, str]],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    method_update_authorized = gate_passed(gates, "method_update_gate")
    weak_update_authorized = gate_passed(gates, "weak_update_authorization_gate")
    odi_validated = claim_status(claims, "ODI robustly predicts drift") == "allowed"
    joint_risk_validated = claim_status(claims, "joint risk predicts drift") == "allowed"
    next_route = "Route A" if method_update_authorized else "Route B"
    final_decision = "GO_WEAK_UPDATE" if method_update_authorized else "NO_GO_METHOD_UPDATE"
    manifest = {
        "status": "OK" if not missing and gates and claims and plan else "FAILED",
        "git_commit": git_commit(),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "final_decision": final_decision,
        "method_update_authorized": bool(method_update_authorized),
        "weak_update_authorized": bool(weak_update_authorized),
        "odi_validated": bool(odi_validated),
        "joint_risk_validated": bool(joint_risk_validated),
        "next_route": next_route,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "negative gate is a valid Day22 outcome; method update remains blocked when authorization is false",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def evidence_row(day, source_file, item, evidence_type, status, key_metric, observed, interpretation, claim_allowed):
    return {
        "day": str(day),
        "source_file": relative_to_root(Path(source_file)),
        "evidence_item": item,
        "evidence_type": evidence_type,
        "status": status,
        "key_metric": key_metric,
        "observed_value": observed,
        "interpretation": interpretation,
        "claim_allowed": claim_allowed,
    }


def gate_row(name, requirement, observed, passed, impact, reason):
    return {
        "gate_name": name,
        "requirement": requirement,
        "observed": observed,
        "passed": str(bool(passed)).lower(),
        "decision_impact": impact,
        "reason": reason,
    }


def claim_row(claim_id, text, status, allowed, forbidden, evidence):
    return {
        "claim_id": claim_id,
        "claim_text": text,
        "status": status,
        "allowed_wording": allowed,
        "forbidden_wording": forbidden,
        "evidence_basis": evidence,
    }


def gate_passed(gates: Sequence[Mapping[str, str]], gate_name: str) -> bool:
    row = find_row(gates, "gate_name", gate_name)
    return row.get("passed") == "true"


def claim_status(claims: Sequence[Mapping[str, str]], claim_text: str) -> str:
    row = find_row(claims, "claim_text", claim_text)
    return row.get("status", "missing")


def find_row(rows: Sequence[Mapping[str, str]], key1: str, value1: str, key2: str | None = None, value2: str | None = None):
    for row in rows:
        if row.get(key1) == value1 and (key2 is None or row.get(key2) == value2):
            return dict(row)
    return {}


def best_day21_row(rows: Sequence[Mapping[str, str]]) -> Dict[str, str]:
    candidates = [row for row in rows if row.get("final_day21_status") == "candidate_supported"]
    if candidates:
        return dict(candidates[0])
    return dict(rows[0]) if rows else {}


def count_rows(rows: Sequence[Mapping[str, str]], key: str, values: set[str]) -> int:
    return sum(str(row.get(key)) in values for row in rows)


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


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
