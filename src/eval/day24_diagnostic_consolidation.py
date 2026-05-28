"""Day 24 diagnostic benchmark consolidation after the Route B pivot."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

ARTIFACT_FIELDNAMES = [
    "artifact_id",
    "day",
    "artifact_type",
    "path",
    "exists",
    "nonempty",
    "role_in_benchmark",
    "claim_supported",
    "limitations",
    "paper_section",
]

PROTOCOL_FIELDNAMES = [
    "protocol_step",
    "step_name",
    "input_artifacts",
    "output_artifacts",
    "purpose",
    "required_for_reproduction",
    "claim_boundary",
    "failure_mode_captured",
]

CLAIM_FIELDNAMES = [
    "claim_id",
    "claim_text",
    "claim_status",
    "allowed_wording",
    "forbidden_wording",
    "primary_evidence",
    "blocking_evidence",
    "paper_section",
]

RISK_FIELDNAMES = [
    "risk_id",
    "reviewer_attack",
    "why_it_matters",
    "evidence_response",
    "remaining_weakness",
    "mitigation_plan",
    "severity",
    "priority",
]

CHECKLIST_FIELDNAMES = [
    "check_id",
    "release_item",
    "status",
    "required_action",
    "blocking",
    "reason",
]

RECOMMENDATION_FIELDNAMES = [
    "recommended_day",
    "recommended_route",
    "task",
    "allowed",
    "reason",
    "blocking_condition",
]


def load_day14_to_day23_artifacts(day14_root: Path, day30_root: Path, reports_root: Path) -> Dict[str, Any]:
    """Load Day 14-23 reports, tables, and manifests for consolidation."""

    paths = {
        "day14_reproduction_manifest": day14_root / "manifests/day14_reproduction_manifest.json",
        "day14_final_manifest": day14_root / "manifests/day14_final_manifest.json",
        "day14_gates": day14_root / "tables/day14_go_nogo_gates.csv",
        "day14_decision": day14_root / "tables/day14_decision_summary.csv",
        "day14_report": reports_root / "day14_go_nogo_report.md",
        "day15_bias_audit": day30_root / "tables/day15_bias_audit.csv",
        "day15_manifest": day30_root / "manifests/day15_bias_audit_manifest.json",
        "day15_report": reports_root / "day15_report.md",
        "day16_summary": day30_root / "tables/day16_unbiased_toy_lio_summary.csv",
        "day16_manifest": day30_root / "manifests/day16_unbiased_toy_lio_manifest.json",
        "day16_report": reports_root / "day16_report.md",
        "day17_trials": day30_root / "tables/day17_unbiased_probe_trials.csv",
        "day17_summary": day30_root / "tables/day17_unbiased_probe_summary.csv",
        "day17_correlations": day30_root / "tables/day17_metric_drift_correlations.csv",
        "day17_manifest": day30_root / "manifests/day17_unbiased_probe_manifest.json",
        "day17_report": reports_root / "day17_report.md",
        "day18_windows": day30_root / "tables/day18_window_metrics.csv",
        "day18_correlations": day30_root / "tables/day18_within_sequence_correlations.csv",
        "day18_summary": day30_root / "tables/day18_sequence_validity_summary.csv",
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
        "day23_failures": day30_root / "tables/day23_failure_taxonomy.csv",
        "day23_claims": day30_root / "tables/day23_claim_consolidation.csv",
        "day23_candidates": day30_root / "tables/day23_metric_redesign_candidates.csv",
        "day23_route": day30_root / "tables/day23_diagnostic_benchmark_route.csv",
        "day23_recommendation": day30_root / "tables/day23_day24_recommendation.csv",
        "day23_manifest": day30_root / "manifests/day23_route_b_pivot_manifest.json",
        "day23_report": reports_root / "day23_route_b_pivot_report.md",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day24 input file(s): "
            + "; ".join(missing)
            + ". Run Day 14-23 scripts before Day 24 diagnostic consolidation."
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


def build_artifact_inventory(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Inventory the required diagnostic benchmark evidence package."""

    entries = [
        ("A14-1", "Day 14", "manifest", "day14_reproduction_manifest", "reproduction provenance", "one-click reproducibility evidence", "smoke plotting/sensitivity scope", "artifact / reproducibility"),
        ("A14-2", "Day 14", "report", "day14_report", "go/no-go boundary", "CONDITIONAL GO with explicit limitations", "legacy toy_lio and merged-correlation confounds", "claims / limitations"),
        ("A15-1", "Day 15", "table", "day15_bias_audit", "bias audit", "legacy toy_lio is diagnostic only", "scene-family axis_bias confound", "bias audit"),
        ("A16-1", "Day 16", "table", "day16_summary", "unbiased protocol check", "axis_bias_mode=none protocol established", "toy probe remains synthetic", "methods / protocol"),
        ("A17-1", "Day 17", "table", "day17_trials", "multi-trial probe", "unbiased exploratory evidence", "not metric validation", "experiments"),
        ("A18-1", "Day 18", "table", "day18_windows", "window-level validation", "within-sequence diagnostic windows", "weak/undefined correlations retained", "experiments"),
        ("A19-1", "Day 19", "table", "day19_pass_fail", "grouped / LOSO validity", "generalization stress test", "LOSO instability and weak effects", "metric validity"),
        ("A20-1", "Day 20", "table", "day20_incremental", "controlled partial validity", "incremental validity screen", "ODI did not pass controlled screen", "metric validity"),
        ("A21-1", "Day 21", "table", "day21_comparison", "joint risk screening", "interpretable risk feature comparison", "all candidates exploratory_not_validated", "metric redesign"),
        ("A22-1", "Day 22", "manifest", "day22_manifest", "formal gate review", "method update blocked by gate", "No-Go method update", "gate review"),
        ("A23-1", "Day 23", "table", "day23_failures", "Route B pivot", "failure taxonomy and route selection", "no method implementation", "pivot / future work"),
    ]
    rows = []
    for aid, day, atype, key, role, claim, limitation, section in entries:
        path = artifacts["paths"][key]
        rows.append(
            {
                "artifact_id": aid,
                "day": day,
                "artifact_type": atype,
                "path": relative_to_root(path),
                "exists": str(path.exists()).lower(),
                "nonempty": str(path.exists() and path.stat().st_size > 0).lower(),
                "role_in_benchmark": role,
                "claim_supported": claim,
                "limitations": limitation,
                "paper_section": section,
            }
        )
    return rows


def build_benchmark_protocol_table(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Describe the diagnostic benchmark protocol from generation through gate review."""

    return [
        protocol_row("P01", "synthetic geometry / minibench generation", "configs/minibench", "data/minibench sequences", "controlled synthetic tunnel/open geometry", True, "synthetic benchmark only", "geometry degeneracy setup"),
        protocol_row("P02", "weak-direction / whitened information analysis", "observations.npz, detector config", "ODI CSV and alignment summaries", "diagnose information spectrum and weak direction", True, "diagnostic geometry evidence, not drift proof", "weak-axis information collapse"),
        protocol_row("P03", "legacy bias audit", "legacy toy_lio and Day14 summaries", "Day15 bias audit table", "separate confounded legacy evidence from main claims", True, "legacy results diagnostic only", "scene-family axis_bias"),
        protocol_row("P04", "unbiased toy_lio protocol", "Day16 config", "unbiased protocol summary", "remove implicit scene-family axis bias", True, "toy probe remains synthetic", "confound control"),
        protocol_row("P05", "multi-trial unbiased probe", "unbiased protocol and Day14 inputs", "Day17 trial tables", "generate exploratory unbiased drift evidence", True, "exploratory evidence only", "trial variability"),
        protocol_row("P06", "window-level within-sequence validation", "Day17 trials, ODI, GT, axis", "Day18 window metrics", "avoid only merged/sequence-level correlation", True, "within-sequence only, undefined cases preserved", "constant metrics and weak rho"),
        protocol_row("P07", "grouped / LOSO validation", "Day18 windows/correlations", "Day19 grouped and LOSO tables", "stress-test generalization across held-out sequences", True, "no robust metric claim if unstable", "group generalization failure"),
        protocol_row("P08", "controlled / partial validity analysis", "Day18/19 outputs", "Day20 partial and permutation tables", "test incremental value after baselines/controls", True, "small rho is not substantive validity", "confounding with baseline metrics"),
        protocol_row("P09", "joint risk screening", "Day18/20 outputs", "Day21 joint-risk tables", "test interpretable combined risk features", True, "candidate only if strict screen passes", "joint feature failure"),
        protocol_row("P10", "go/no-go gate review", "Day15-21 evidence", "Day22 gate decision", "block unsupported method updates", True, "negative gate is valid evidence", "overclaim prevention"),
        protocol_row("P11", "Route B pivot", "Day18-22 evidence", "Day23 pivot tables", "convert No-Go into diagnostic benchmark route", True, "no estimator implementation", "paper-route consolidation"),
    ]


def build_paper_claim_map(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Map paper claims to allowed, forbidden, diagnostic-only, or exploratory-only status."""

    day22_claims = {row.get("claim_text", ""): row for row in artifacts["day22_claims"]}
    day23_claims = {row.get("claim_text", ""): row for row in artifacts["day23_claims"]}
    return [
        claim_row("C24-01", "weak-direction geometry can be diagnosed in synthetic tunnel-like scenes", "allowed", "Synthetic tunnel-like scenes expose weak information directions in a reproducible diagnostic setting.", "Do not present this as real-world estimator validation.", "Day9/Day14 weak-direction and alignment artifacts", "synthetic scope", "benchmark design / results"),
        claim_row("C24-02", "legacy biased toy_lio is diagnostic only", "diagnostic_only", "Legacy biased toy_lio is useful only as a bias-audit lesson.", "Do not use legacy biased toy_lio as main metric evidence.", "Day15 bias audit", "scene-family-dependent axis_bias", "limitations"),
        claim_row("C24-03", "unbiased toy_lio protocol is established", "allowed", "The unbiased toy_lio protocol is established for synthetic diagnostic probes.", "Do not call toy_lio a real LIO estimator.", "Day16 protocol and Day17-18 zero-bias rows", "synthetic probe only", "methods"),
        claim_row("C24-04", "ODI robustly predicts drift", "forbidden", "ODI remains an exploratory diagnostic in this package.", day22_claims.get("ODI robustly predicts drift", {}).get("forbidden_wording", "Do not state this robust ODI claim."), "weak-direction geometry and exploratory merged signals", "Day19 LOSO, Day20 controlled screen, Day23 claim boundary", "not allowed"),
        claim_row("C24-05", "ODI is superior to AIS/lambda_min", "forbidden", "ODI should be reported beside AIS, lambda_min_clamped, and condition_number.", "Do not claim ODI superiority over AIS/lambda_min_clamped.", "metric comparison tables", "AIS/lambda_min/condition_number remain competitive", "not allowed"),
        claim_row("C24-06", "joint risk predicts drift", "forbidden", "Joint risk features are exploratory diagnostics only.", "Do not present joint risk as validated drift prediction.", "Day21 joint risk tables", "all joint features exploratory_not_validated", "not allowed"),
        claim_row("C24-07", "Degen-LIO estimator update is ready", "forbidden", "The current package supports diagnostics, not an estimator update.", "Do not claim a validated Degen-LIO estimator method.", "Day22 method gate and Day23 Route B", "method_update_authorized=false", "not allowed"),
        claim_row("C24-08", "diagnostic benchmark package is reproducible", "conditional", "The diagnostic package is reproducible under the recorded scripts/manifests and smoke CI plotting path.", "Do not imply full real-data or estimator validation.", "Day13/Day14 reproduction and Day15-23 manifests", "smoke plot/sensitivity mode and synthetic scope", "artifact / reproducibility"),
        claim_row("C24-09", "negative metric-validity evidence is informative", "allowed", "Negative validity screens identify where metric redesign is needed.", "Do not hide or weaken the No-Go outcome.", "Day18-23 failure and gate tables", "limited benchmark diversity", "discussion / failure analysis"),
    ]


def build_reviewer_risk_register(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    """List reviewer attacks and prepared evidence-grounded responses."""

    return [
        risk_row("R01", "synthetic-only benchmark", "Reviewers may reject broad claims from synthetic scenes.", "Scope claims as diagnostic benchmark and include reproducible configs.", "No real-data validation yet.", "Add real-data sanity checks only after metric claims are bounded.", "high", "high"),
        risk_row("R02", "toy_lio is not real LIO", "Toy trajectories cannot validate estimator performance.", "State toy_lio is a synthetic probe and keep legacy/unbiased audit visible.", "Estimator coupling remains untested.", "Use toy_lio only for diagnostic evidence.", "high", "high"),
        risk_row("R03", "ODI failed controlled validity", "A proposed metric that fails strict screens cannot support method claims.", "Report Day20 as negative evidence and compare baselines fairly.", "ODI may need redesign or temporal features.", "Move ODI into exploratory diagnostic role.", "critical", "high"),
        risk_row("R04", "joint risk failed gate", "Combined features did not rescue the method gate.", "Keep Day21 all-candidate status and no-ODI comparisons.", "Fixed equal-weight formulas may be too weak.", "Treat joint risk as redesign input, not validation.", "critical", "high"),
        risk_row("R05", "no estimator update", "Method novelty is reduced without a new update.", "Frame the contribution as benchmark/failure-analysis package.", "Venue fit may be harder.", "Prepare a diagnostic benchmark paper route.", "medium", "high"),
        risk_row("R06", "smoke vs real plots", "CI uses smoke plotting/sensitivity for stability.", "Manifest records smoke mode and real scripts remain available separately.", "Visual regeneration may need environment care.", "Document both CI and real-render commands.", "medium", "medium"),
        risk_row("R07", "small number of scene families", "Four synthetic families limit generality.", "Use the limitation as a benchmark expansion item.", "Metric conclusions remain narrow.", "Add families before stronger claims.", "medium", "medium"),
        risk_row("R08", "overclaiming risk", "Unsupported drift/method claims would be easy to attack.", "Claim map explicitly marks forbidden and diagnostic-only claims.", "Requires discipline in abstract/conclusion wording.", "Use Day24 claim map as writing guardrail.", "high", "high"),
        risk_row("R09", "reproducibility risk", "Generated artifacts and manifests must be rebuildable.", "Day13/14 reproduction and pytest chain exist; Day24 inventory lists artifacts.", "Generated data volume and smoke modes need clear packaging.", "Use release checklist before packaging.", "medium", "high"),
    ]


def build_release_checklist(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Define release checks for a diagnostic benchmark package."""

    return [
        checklist_row("K01", "README explains diagnostic benchmark scope", "pending", "Add scope, No-Go method gate, and allowed/forbidden claims to README.", True, "prevents method overclaiming"),
        checklist_row("K02", "reproduction commands are complete", "partial", "List check_env, pytest, reproduce_day14, Day15-24 scripts.", True, "reviewers need exact commands"),
        checklist_row("K03", "Day 14-24 manifests are complete", "pass", "Keep manifests committed or generated by scripts.", True, "traceability requirement"),
        checklist_row("K04", "results/day30 key CSV can be rebuilt", "pass", "Maintain Day15-24 script chain and configs.", True, "diagnostic evidence is table-driven"),
        checklist_row("K05", "forbidden claims documented", "pass", "Use Day22 and Day24 claim maps in writing.", True, "guards against unsupported claims"),
        checklist_row("K06", "no method update is explicit", "pass", "Keep method_update_authorized=false in manifests and report.", True, "Day22/23/24 route constraint"),
        checklist_row("K07", "raw trajectories commit policy decided", "pending", "Document whether raw trajectories are generated or packaged.", False, "large generated artifacts may be excluded"),
        checklist_row("K08", "full pytest passes locally", "pass", "Run python3 -m pytest -q before release.", True, "baseline quality gate"),
        checklist_row("K09", "exclude .git from final package", "pending", "Package release archive without .git unless explicitly sharing repository history.", True, "avoid leaking repository internals"),
        checklist_row("K10", "exclude __pycache__ from final package", "pass", "Keep __pycache__ ignored and absent from release archive.", True, "clean package hygiene"),
        checklist_row("K11", "exclude .pytest_cache from final package", "pass", "Keep .pytest_cache ignored and absent from release archive.", True, "clean package hygiene"),
    ]


def derive_day25_recommendation(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Recommend Day 25 route without authorizing method implementation."""

    method_allowed = bool(artifacts["day22_manifest"].get("method_update_authorized", False))
    return [
        {
            "recommended_day": "Day 25",
            "recommended_route": "Route B1: diagnostic benchmark paper outline / figure-table plan",
            "task": "turn Day14-24 evidence into paper sections, table plan, and claim-boundary figures",
            "allowed": str(not method_allowed).lower(),
            "reason": "Day24 package is a diagnostic benchmark route with explicit No-Go method boundary",
            "blocking_condition": "none if method_update_authorized remains false",
        },
        {
            "recommended_day": "Day 25",
            "recommended_route": "Route B2: metric redesign prototype review",
            "task": "review temporal/excitation-normalized metric candidates before any implementation",
            "allowed": str(not method_allowed).lower(),
            "reason": "Day23 identified redesign candidates but none are validated metrics",
            "blocking_condition": "must remain analysis-only until a future gate passes",
        },
        {
            "recommended_day": "Day 25",
            "recommended_route": "weak-subspace update implementation",
            "task": "implement estimator update",
            "allowed": "false",
            "reason": "blocked by Day22 No-Go and Day24 consolidation",
            "blocking_condition": "requires future method_update_authorized=true",
        },
    ]


def write_day24_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    inventory: Sequence[Mapping[str, str]],
    protocol: Sequence[Mapping[str, str]],
    claims: Sequence[Mapping[str, str]],
    risks: Sequence[Mapping[str, str]],
    checklist: Sequence[Mapping[str, str]],
    recommendation: Sequence[Mapping[str, str]],
    artifacts: Mapping[str, Any],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    method_update_authorized = bool(artifacts["day22_manifest"].get("method_update_authorized", False))
    weak_update_authorized = bool(artifacts["day22_manifest"].get("weak_update_authorized", False))
    route = next((row["recommended_route"] for row in recommendation if row["allowed"] == "true"), "none")
    manifest = {
        "status": "OK" if not missing and inventory and protocol and claims and risks and checklist else "FAILED",
        "git_commit": git_commit(),
        "source_route": "diagnostic_benchmark_consolidation",
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "artifact_count": len(inventory),
        "protocol_step_count": len(protocol),
        "claim_count": len(claims),
        "reviewer_risk_count": len(risks),
        "release_check_count": len(checklist),
        "recommended_day25_route": route,
        "method_update_authorized": method_update_authorized,
        "weak_update_authorized": weak_update_authorized,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "diagnostic benchmark package with explicit claim boundaries; no estimator method update authorized",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def protocol_row(step, name, inputs, outputs, purpose, required, boundary, failure):
    return {
        "protocol_step": step,
        "step_name": name,
        "input_artifacts": inputs,
        "output_artifacts": outputs,
        "purpose": purpose,
        "required_for_reproduction": str(bool(required)).lower(),
        "claim_boundary": boundary,
        "failure_mode_captured": failure,
    }


def claim_row(cid, text, status, allowed, forbidden, evidence, blocking, section):
    return {
        "claim_id": cid,
        "claim_text": text,
        "claim_status": status,
        "allowed_wording": allowed,
        "forbidden_wording": forbidden,
        "primary_evidence": evidence,
        "blocking_evidence": blocking,
        "paper_section": section,
    }


def risk_row(rid, attack, matters, response, weakness, mitigation, severity, priority):
    return {
        "risk_id": rid,
        "reviewer_attack": attack,
        "why_it_matters": matters,
        "evidence_response": response,
        "remaining_weakness": weakness,
        "mitigation_plan": mitigation,
        "severity": severity,
        "priority": priority,
    }


def checklist_row(cid, item, status, action, blocking, reason):
    return {
        "check_id": cid,
        "release_item": item,
        "status": status,
        "required_action": action,
        "blocking": str(bool(blocking)).lower(),
        "reason": reason,
    }


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
