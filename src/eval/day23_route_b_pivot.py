"""Day 23 Route B pivot analysis after the Day 22 No-Go gate."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

FAILURE_FIELDNAMES = [
    "failure_id",
    "failure_source_day",
    "failure_type",
    "affected_claim",
    "observed_evidence",
    "root_cause_hypothesis",
    "severity",
    "can_be_fixed_by_more_trials",
    "can_be_fixed_by_metric_redesign",
    "can_be_fixed_by_method_update",
    "recommended_response",
]

CLAIM_FIELDNAMES = [
    "claim_id",
    "claim_text",
    "current_status",
    "allowed_wording",
    "forbidden_wording",
    "supporting_evidence",
    "blocking_evidence",
    "paper_usage",
]

REDESIGN_FIELDNAMES = [
    "candidate_id",
    "candidate_name",
    "motivation",
    "uses_ODI",
    "uses_AIS",
    "uses_lambda_min",
    "uses_condition_number",
    "uses_motion_excitation",
    "uses_temporal_derivative",
    "uses_window_instability",
    "expected_advantage",
    "main_risk",
    "required_next_test",
    "priority",
]

BENCHMARK_FIELDNAMES = [
    "route_item",
    "description",
    "evidence_available",
    "missing_evidence",
    "paper_claim_strength",
    "implementation_cost",
    "reviewer_risk",
    "recommended_priority",
]

RECOMMENDATION_FIELDNAMES = [
    "recommended_day",
    "recommended_route",
    "task",
    "reason",
    "allowed",
    "blocking_condition",
]


def load_day18_to_day22_artifacts(day30_root: Path, reports_root: Path) -> Dict[str, Any]:
    """Load Day 18-22 tables, manifests, and reports needed for Route B."""

    paths = {
        "day18_summary": day30_root / "tables/day18_sequence_validity_summary.csv",
        "day18_correlations": day30_root / "tables/day18_within_sequence_correlations.csv",
        "day18_manifest": day30_root / "manifests/day18_within_sequence_manifest.json",
        "day18_report": reports_root / "day18_report.md",
        "day19_grouped": day30_root / "tables/day19_grouped_metric_summary.csv",
        "day19_loso": day30_root / "tables/day19_loso_selection_results.csv",
        "day19_pass_fail": day30_root / "tables/day19_metric_pass_fail_summary.csv",
        "day19_manifest": day30_root / "manifests/day19_grouped_loso_manifest.json",
        "day19_report": reports_root / "day19_report.md",
        "day20_partial": day30_root / "tables/day20_partial_correlations.csv",
        "day20_incremental": day30_root / "tables/day20_incremental_validity_summary.csv",
        "day20_manifest": day30_root / "manifests/day20_controlled_partial_manifest.json",
        "day20_report": reports_root / "day20_report.md",
        "day21_comparison": day30_root / "tables/day21_joint_risk_comparison.csv",
        "day21_manifest": day30_root / "manifests/day21_joint_risk_manifest.json",
        "day21_report": reports_root / "day21_report.md",
        "day22_evidence": day30_root / "tables/day22_evidence_matrix.csv",
        "day22_gates": day30_root / "tables/day22_gate_decision.csv",
        "day22_claims": day30_root / "tables/day22_claim_status.csv",
        "day22_plan": day30_root / "tables/day22_next_action_plan.csv",
        "day22_manifest": day30_root / "manifests/day22_gate_review_manifest.json",
        "day22_report": reports_root / "day22_gate_review.md",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day23 input file(s): "
            + "; ".join(missing)
            + ". Run Day 18-22 validation before Day 23 Route B pivot."
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


def build_failure_taxonomy(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Separate single-metric, joint-risk, and gate-level failures."""

    day18_summary = artifacts["day18_summary"]
    day19_odi = find_row(artifacts["day19_pass_fail"], "metric_name", "ODI_median", "target_name", "axis_drift_rate")
    day20_odi = find_row(artifacts["day20_incremental"], "metric_name", "ODI_median", "target_name", "axis_drift_rate")
    day21_best = best_day21_row(artifacts["day21_comparison"])
    method_gate = find_row(artifacts["day22_gates"], "gate_name", "method_update_gate")
    weak_gate = find_row(artifacts["day22_gates"], "gate_name", "weak_update_authorization_gate")
    weak_rho_rows = [
        f"{row['sequence_id']}:{row.get('ODI_axis_drift_rho', 'nan')}"
        for row in day18_summary
    ]
    return [
        failure_row(
            "F18",
            "Day 18",
            "weak_within_sequence_effect",
            "single metrics explain axis drift",
            "ODI axis rho by sequence = " + "; ".join(weak_rho_rows),
            "window-level spectral values vary weakly or inconsistently relative to drift targets",
            "high",
            "unlikely",
            "yes",
            "no",
            "redesign metrics around temporal instability and excitation, not update logic",
        ),
        failure_row(
            "F19",
            "Day 19",
            "grouped_loso_instability",
            "metric validity generalizes across held-out sequences",
            day19_odi.get("reason", "ODI remains exploratory under grouped / LOSO screening"),
            "sequence identity and geometry dominate more than a single stable risk metric",
            "high",
            "partially",
            "yes",
            "no",
            "keep LOSO negative evidence and test grouped diagnostic descriptors",
        ),
        failure_row(
            "F20",
            "Day 20",
            "controlled_incremental_failure",
            "ODI has incremental explanatory value",
            day20_odi.get("reason", "ODI controlled incremental validity failed"),
            "ODI overlaps with information metrics and loses effect size after controls",
            "critical",
            "unlikely",
            "yes",
            "no",
            "treat ODI as one diagnostic component, not a standalone control signal",
        ),
        failure_row(
            "F21",
            "Day 21",
            "joint_risk_candidate_failure",
            "joint risk predicts drift well enough for method gating",
            f"best={day21_best.get('feature_name', 'none')} status={day21_best.get('final_day21_status', 'missing')}",
            "fixed combinations do not pass controlled effect-size/permutation screens; no-ODI can be as strong",
            "critical",
            "partially",
            "yes",
            "no",
            "separate diagnostic benchmark paper route from method update claims",
        ),
        failure_row(
            "F22",
            "Day 22",
            "method_gate_blocked",
            "weak-subspace update can be implemented",
            f"method_gate={method_gate.get('passed', 'false')}; weak_gate={weak_gate.get('passed', 'false')}",
            "authorization requires a validated joint risk candidate and explicit weak update authorization",
            "critical",
            "no",
            "yes",
            "no",
            "follow Route B: diagnostic consolidation or metric redesign review",
        ),
    ]


def build_claim_consolidation_table(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Consolidate what can and cannot be claimed after the No-Go gate."""

    day22_claims = {row["claim_text"]: row for row in artifacts["day22_claims"]}
    return [
        claim_row(
            "CL01",
            "unbiased toy_lio protocol is established",
            "allowed",
            "The unbiased toy_lio protocol is established for synthetic diagnostic probes.",
            "Do not call unbiased toy_lio a real LIO system.",
            "Day 16 protocol plus Day 17-18 unbiased rows",
            "none",
            "methods / reproducibility section",
        ),
        claim_row(
            "CL02",
            "legacy toy_lio is diagnostic only",
            "allowed",
            "Legacy biased toy_lio is diagnostic-only evidence.",
            "Do not use legacy biased toy_lio as main metric validity evidence.",
            "Day 15 bias audit",
            "scene-family-dependent axis_bias",
            "limitations / audit section",
        ),
        claim_row(
            "CL03",
            "ODI robustly predicts drift",
            "forbidden",
            "ODI remains exploratory under current synthetic validation.",
            day22_claims.get("ODI robustly predicts drift", {}).get(
                "forbidden_wording",
                "Do not state robust ODI drift prediction.",
            ),
            "weak-direction geometry and merged signals",
            "Day 19 grouped/LOSO and Day 20 controlled screens",
            "not allowed as a paper claim",
        ),
        claim_row(
            "CL04",
            "ODI is superior to AIS/lambda_min",
            "forbidden",
            "ODI should be compared with AIS, lambda_min_clamped, and condition_number.",
            "Do not claim ODI superiority.",
            "none",
            "AIS/lambda_min/condition_number remain strong competitors",
            "not allowed as a paper claim",
        ),
        claim_row(
            "CL05",
            "joint risk predicts drift",
            "forbidden",
            "Joint risk features are exploratory diagnostics.",
            "Do not present joint risk as validated drift prediction.",
            "Day 21 interpretable feature table",
            "Day 21 all joint risks exploratory_not_validated",
            "candidate diagnostic, not conclusion",
        ),
        claim_row(
            "CL06",
            "weak-subspace update is authorized",
            "forbidden",
            "Weak-subspace update is not authorized by Day 22.",
            "Do not implement or claim update authorization.",
            "none",
            "Day 22 method_update_authorized=false",
            "not allowed",
        ),
        claim_row(
            "CL07",
            "Degen-LIO method is ready",
            "forbidden",
            "The current evidence supports diagnostic benchmark / redesign planning only.",
            "Do not state Degen-LIO method readiness.",
            "reproducible diagnostic chain",
            "No-Go method gate and lack of validated risk metric",
            "not allowed",
        ),
        claim_row(
            "CL08",
            "diagnostic benchmark package is reproducible",
            "conditional",
            "The synthetic diagnostic package is reproducible and useful for failure analysis.",
            "Do not overstate it as real-world LIO validation.",
            "Day 13-22 reproducibility and diagnostics",
            "synthetic-only scope",
            "allowed with scope limits",
        ),
    ]


def propose_metric_redesign_candidates(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    """List unvalidated metric/risk redesign candidates for Day 24 review."""

    return [
        redesign_row("M01", "temporal_ODI_delta", "static ODI was weak; test change over time", True, False, False, False, False, True, True, "captures degradation dynamics", "can amplify noise", "windowed permutation and LOSO", "high"),
        redesign_row("M02", "ODI_instability_over_window", "window-level ODI variation may matter more than median", True, False, False, False, False, True, True, "separates stable degeneracy from sudden risk", "may correlate with sequence artifacts", "within-sequence controlled screen", "high"),
        redesign_row("M03", "excitation_normalized_lambda", "lambda_min needs motion/path normalization", False, False, True, False, True, False, False, "normalizes geometry by available motion excitation", "requires robust excitation estimate", "controlled partial with path/motion controls", "high"),
        redesign_row("M04", "information_drop_rate", "condition and lambda are competitive but static", False, True, True, True, False, True, True, "uses information loss trend rather than absolute scale", "sensitive to simulator noise", "LOSO across held-out sequences", "medium"),
        redesign_row("M05", "weak_alignment_instability", "alignment is strong but not enough alone", False, False, False, False, False, True, True, "tracks unstable weak direction orientation", "undefined for open control frames", "NaN-safe window validation", "medium"),
        redesign_row("M06", "hybrid_failure_detector_no_method_update", "diagnostic detector can be useful without control update", True, True, True, True, True, False, True, "paper-safe diagnostic output without method claim", "reviewers may expect real data", "benchmark task definition", "high"),
        redesign_row("M07", "diagnostic_score_not_control_gain", "avoid unvalidated control coupling", True, True, True, True, True, False, True, "separates detection score from estimator intervention", "less novel than method update", "diagnostic benchmark acceptance criteria", "high"),
    ]


def build_diagnostic_benchmark_route(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Define a paper-safe diagnostic benchmark route from existing evidence."""

    return [
        benchmark_row("synthetic degeneracy benchmark", "Four-sequence minibench with GT, observations, ODI, toy trajectories, and windows", "Day 1-22 generated artifacts", "more scene variants and real-data sanity check", "moderate", "medium", "synthetic-only critique", "high"),
        benchmark_row("weak-direction geometry analysis", "Information-spectrum weak direction aligns with tunnel/local axis", "Day 9 alignment summaries and figures", "broader geometry families", "moderate", "low", "not enough estimator coupling", "high"),
        benchmark_row("biased vs unbiased toy_lio lesson", "Legacy bias audit plus unbiased protocol explains confound risk", "Day 15-17 outputs", "larger unbiased trial set", "strong diagnostic lesson", "low", "toy probe is not real LIO", "high"),
        benchmark_row("metric validity negative result", "ODI, baselines, and joint risk fail strict controlled gate", "Day 18-22 tables", "more benchmark diversity", "moderate but honest", "low", "negative-result acceptance risk", "high"),
        benchmark_row("claim boundary table", "Allowed/forbidden claims prevent overclaiming", "Day 22 and Day 23 claim tables", "reviewer-facing wording polish", "strong reproducibility appendix", "low", "may look conservative", "medium"),
        benchmark_row("reproducible diagnostic package", "One repository contains configs, scripts, tests, manifests, and reports", "Day 13-22 manifests/tests", "packaging and README", "strong artifact value", "medium", "artifact maintenance burden", "high"),
        benchmark_row("no method update yet", "No-Go gate prevents unvalidated estimator changes", "Day 22 method_update_authorized=false", "clear future-work plan", "high integrity", "low", "less method novelty", "high"),
    ]


def derive_day24_recommendation(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Recommend Day 24 Route B next step."""

    method_allowed = bool(artifacts["day22_manifest"].get("method_update_authorized", False))
    return [
        {
            "recommended_day": "Day 24",
            "recommended_route": "diagnostic benchmark consolidation",
            "task": "consolidate benchmark package, claim boundaries, and negative metric validity evidence",
            "reason": "Day 22 selected Route B and Day 23 taxonomy shows diagnostic evidence is paper-usable",
            "allowed": str(not method_allowed).lower(),
            "blocking_condition": "none if method_update_gate remains false",
        },
        {
            "recommended_day": "Day 24",
            "recommended_route": "metric redesign prototype review",
            "task": "review temporal/excitation-normalized diagnostic metric candidates without estimator update",
            "reason": "single ODI and joint risks failed strict screens but redesign candidates are plausible",
            "allowed": str(not method_allowed).lower(),
            "blocking_condition": "must not implement weak-subspace update",
        },
        {
            "recommended_day": "Day 24",
            "recommended_route": "weak-subspace update implementation",
            "task": "implement estimator update logic",
            "reason": "blocked by Day 22 No-Go gate",
            "allowed": "false",
            "blocking_condition": "requires future gate with method_update_authorized=true",
        },
    ]


def write_day23_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    failures: Sequence[Mapping[str, str]],
    claims: Sequence[Mapping[str, str]],
    candidates: Sequence[Mapping[str, str]],
    benchmark: Sequence[Mapping[str, str]],
    recommendation: Sequence[Mapping[str, str]],
    artifacts: Mapping[str, Any],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    method_update_authorized = bool(artifacts["day22_manifest"].get("method_update_authorized", False))
    weak_update_authorized = bool(artifacts["day22_manifest"].get("weak_update_authorized", False))
    route = next((row["recommended_route"] for row in recommendation if row["allowed"] == "true"), "none")
    manifest = {
        "status": "OK" if failures and claims and candidates and benchmark and recommendation and not missing else "FAILED",
        "git_commit": git_commit(),
        "source_route": "Route_B",
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "failure_count": len(failures),
        "claim_count": len(claims),
        "metric_redesign_candidate_count": len(candidates),
        "diagnostic_route_item_count": len(benchmark),
        "recommended_day24_route": route,
        "method_update_authorized": method_update_authorized,
        "weak_update_authorized": weak_update_authorized,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "No-Go is evidence; continue diagnostic benchmark consolidation or metric redesign review",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def failure_row(fid, day, failure_type, claim, evidence, cause, severity, more_trials, redesign, method, response):
    return {
        "failure_id": fid,
        "failure_source_day": day,
        "failure_type": failure_type,
        "affected_claim": claim,
        "observed_evidence": evidence,
        "root_cause_hypothesis": cause,
        "severity": severity,
        "can_be_fixed_by_more_trials": more_trials,
        "can_be_fixed_by_metric_redesign": redesign,
        "can_be_fixed_by_method_update": method,
        "recommended_response": response,
    }


def claim_row(cid, text, status, allowed, forbidden, supporting, blocking, usage):
    return {
        "claim_id": cid,
        "claim_text": text,
        "current_status": status,
        "allowed_wording": allowed,
        "forbidden_wording": forbidden,
        "supporting_evidence": supporting,
        "blocking_evidence": blocking,
        "paper_usage": usage,
    }


def redesign_row(cid, name, motivation, odi, ais, lamb, cond, motion, temporal, instability, advantage, risk, test, priority):
    return {
        "candidate_id": cid,
        "candidate_name": name,
        "motivation": motivation,
        "uses_ODI": str(bool(odi)).lower(),
        "uses_AIS": str(bool(ais)).lower(),
        "uses_lambda_min": str(bool(lamb)).lower(),
        "uses_condition_number": str(bool(cond)).lower(),
        "uses_motion_excitation": str(bool(motion)).lower(),
        "uses_temporal_derivative": str(bool(temporal)).lower(),
        "uses_window_instability": str(bool(instability)).lower(),
        "expected_advantage": advantage,
        "main_risk": risk,
        "required_next_test": test,
        "priority": priority,
    }


def benchmark_row(item, description, available, missing, strength, cost, risk, priority):
    return {
        "route_item": item,
        "description": description,
        "evidence_available": available,
        "missing_evidence": missing,
        "paper_claim_strength": strength,
        "implementation_cost": cost,
        "reviewer_risk": risk,
        "recommended_priority": priority,
    }


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


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
