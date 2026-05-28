"""Day 25 diagnostic benchmark paper outline and figure/table plan."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

TITLE_FIELDNAMES = [
    "candidate_id",
    "title_candidate",
    "paper_type",
    "positioning",
    "strength",
    "main_risk",
    "recommended",
    "reason",
]

CONTRIBUTION_FIELDNAMES = [
    "contribution_id",
    "contribution_text",
    "claim_status",
    "supporting_evidence",
    "blocking_evidence",
    "paper_section",
    "risk_level",
    "allowed_wording",
]

SECTION_FIELDNAMES = [
    "section_id",
    "section_title",
    "section_goal",
    "key_points",
    "required_evidence",
    "figures_tables",
    "claim_boundary",
    "writing_risk",
]

FIGURE_TABLE_FIELDNAMES = [
    "item_id",
    "item_type",
    "proposed_caption",
    "source_artifact",
    "purpose",
    "must_show",
    "must_not_claim",
    "paper_section",
    "priority",
]

STORYLINE_FIELDNAMES = [
    "story_step",
    "question",
    "experiment_or_analysis",
    "evidence_artifact",
    "observed_result",
    "interpretation",
    "next_step",
    "claim_allowed",
]

CLAIM_BOUNDARY_FIELDNAMES = [
    "claim_id",
    "claim_text",
    "status",
    "allowed_wording",
    "forbidden_wording",
    "where_to_use",
    "where_to_avoid",
    "evidence_basis",
]

REPRO_FIELDNAMES = [
    "repro_step",
    "command",
    "expected_outputs",
    "required_inputs",
    "runtime_expectation",
    "notes",
]

REVIEWER_FIELDNAMES = [
    "risk_id",
    "reviewer_attack",
    "short_response",
    "evidence_to_cite",
    "remaining_limitation",
    "planned_mitigation",
]

RECOMMENDATION_FIELDNAMES = [
    "recommended_day",
    "recommended_route",
    "task",
    "allowed",
    "reason",
    "blocking_condition",
]


def load_day14_to_day24_artifacts(day14_root: Path, day30_root: Path, reports_root: Path) -> Dict[str, Any]:
    """Load the diagnostic benchmark evidence used by the paper outline."""

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
        "day22_claims": day30_root / "tables/day22_claim_status.csv",
        "day22_gates": day30_root / "tables/day22_gate_decision.csv",
        "day22_plan": day30_root / "tables/day22_next_action_plan.csv",
        "day22_manifest": day30_root / "manifests/day22_gate_review_manifest.json",
        "day22_report": reports_root / "day22_gate_review.md",
        "day23_failures": day30_root / "tables/day23_failure_taxonomy.csv",
        "day23_claims": day30_root / "tables/day23_claim_consolidation.csv",
        "day23_candidates": day30_root / "tables/day23_metric_redesign_candidates.csv",
        "day23_route": day30_root / "tables/day23_diagnostic_benchmark_route.csv",
        "day23_manifest": day30_root / "manifests/day23_route_b_pivot_manifest.json",
        "day23_report": reports_root / "day23_route_b_pivot_report.md",
        "day24_inventory": day30_root / "tables/day24_artifact_inventory.csv",
        "day24_protocol": day30_root / "tables/day24_benchmark_protocol.csv",
        "day24_claims": day30_root / "tables/day24_paper_claim_map.csv",
        "day24_risks": day30_root / "tables/day24_reviewer_risk_register.csv",
        "day24_checklist": day30_root / "tables/day24_release_checklist.csv",
        "day24_recommendation": day30_root / "tables/day24_day25_recommendation.csv",
        "day24_manifest": day30_root / "manifests/day24_diagnostic_consolidation_manifest.json",
        "day24_report": reports_root / "day24_diagnostic_consolidation_report.md",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day25 input file(s): "
            + "; ".join(missing)
            + ". Run Day 14-24 scripts before Day 25 paper outline."
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


def build_title_positioning_candidates(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        title_row("T01", "A Diagnostic Benchmark for LiDAR-Inertial Degeneracy in Synthetic Tunnel-Like Scenes", "diagnostic benchmark", "benchmark and failure-analysis package", "clear scope and reproducible artifact value", "synthetic-only scope", True, "best matches the Day 24 consolidation route"),
        title_row("T02", "Failure Analysis of Metric Validity under Synthetic Tunnel-Like Degeneracy", "failure analysis", "negative metric-validity study", "foregrounds strict validation and No-Go result", "may sound too negative without benchmark framing", False, "strong secondary framing for discussion"),
        title_row("T03", "A Reproducible Degeneracy Diagnosis Package for LIO Metric Stress Testing", "artifact paper", "reproducible diagnostic package", "emphasizes scripts, manifests, and claim boundaries", "less direct paper hook", False, "useful if targeting artifact-focused venue"),
        title_row("T04", "Degen-LIO Estimator Update for Robust Tunnel Navigation", "method paper", "validated estimator method", "none", "implies a method update that is not authorized", False, "reject because it overclaims current evidence"),
    ]


def build_contribution_map(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        contribution_row("C01", "synthetic degeneracy benchmark", "allowed", "Day14 minibench, manifests, and diagnostic tables", "synthetic-only scope", "Benchmark", "medium", "We provide a reproducible synthetic diagnostic benchmark for controlled degeneracy cases."),
        contribution_row("C02", "weak-direction / whitened information diagnostic protocol", "allowed", "Day6-9 ODI/weak-direction artifacts and Day24 protocol", "not estimator validation", "Diagnostics", "medium", "We analyze whitened information spectra and weak-direction geometry as diagnostics."),
        contribution_row("C03", "legacy bias audit and unbiased toy_lio protocol", "allowed", "Day15 bias audit and Day16 unbiased protocol", "toy_lio is synthetic and not real LIO", "Bias Audit", "low", "We expose the legacy axis-bias confound and replace it with an unbiased probe protocol."),
        contribution_row("C04", "strict metric validity negative evidence", "allowed", "Day18-21 validation tables", "limited scene families", "Metric Validity", "high", "We report strict negative evidence rather than turning weak correlations into claims."),
        contribution_row("C05", "claim-boundary and gate-review framework", "allowed", "Day22-24 gate and claim maps", "conservative framing may reduce method novelty", "Gate Review", "medium", "We formalize allowed, conditional, exploratory, diagnostic-only, and forbidden claims."),
        contribution_row("C06", "reproducibility package", "conditional", "Day13/14 manifests and Day15-24 scripts", "smoke plotting/sensitivity mode in reproduction", "Artifact", "medium", "We release scripts, configs, tables, and manifests with explicit reproduction commands."),
        contribution_row("C07", "validated estimator update", "forbidden", "none", "Day22/24 method_update_authorized=false", "Not Included", "critical", "Do not present an estimator update as a contribution."),
    ]


def build_section_outline(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        section_row("S01", "Introduction", "Position the work as diagnostic benchmark / failure analysis", "degeneracy matters; previous overclaims are risky; this paper emphasizes reproducible boundaries", "Day14 decision and Day24 claim map", "T01, F01", "do not imply method validation", "overpromising novelty"),
        section_row("S02", "Related Work", "Connect LIO degeneracy metrics, benchmarks, and reproducible artifacts", "observability, information matrices, synthetic benchmarks, failure analysis", "literature plus internal claim map", "none", "avoid claiming a new estimator", "missing broader citations"),
        section_row("S03", "Problem Formulation and Diagnostic Objective", "Define diagnostic objective and 6DoF pose-block information scope", "pose-block spectrum; weak direction; metric validity as diagnostic target", "Day6-9 definitions", "F02, Table P1", "diagnostic objective only", "too close to method framing"),
        section_row("S04", "Synthetic Degeneracy Benchmark", "Describe OC/ST/CT/RT scenes and reproducibility", "geometry, GT, observations, configs, seeds, manifests", "Day14/Day24 artifact inventory", "F01, Table B1", "synthetic benchmark only", "synthetic-only attack"),
        section_row("S05", "Whitened Information and Weak-Direction Diagnostics", "Show information spectra and weak-axis alignment", "spectrum concentration; local-axis alignment; unreliable OC handling", "Day9/Day14 figures and tables", "F02, F03", "geometry diagnosis, not drift proof", "ODI overclaim risk"),
        section_row("S06", "Bias Audit and Unbiased Toy Probe", "Explain legacy bias and unbiased protocol", "legacy scene-family bias; all-zero applied bias; multi-trial probe", "Day15-17 outputs", "F04, Table B2", "toy_lio is a probe, not real LIO", "toy_lio attack"),
        section_row("S07", "Metric Validity Stress Tests", "Report Day18-21 validation including negative results", "within-sequence, grouped/LOSO, controlled partial, joint risk", "Day18-21 tables", "F05-F08, Tables V1-V4", "negative evidence is informative", "temptation to hide failures"),
        section_row("S08", "Go/No-Go Gate and Claim Boundary", "Formalize why method update is blocked", "Day22 No-Go; Day23/24 Route B; allowed/forbidden claims", "Day22-24 tables", "Table G1, Table C1", "No-Go is valid outcome", "appearing too conservative"),
        section_row("S09", "Discussion and Limitations", "Discuss reviewer risks and future redesign routes", "synthetic-only, toy_lio, metric failure, no estimator update", "Day24 risk register", "Table R1", "future work must remain gated", "reviewer skepticism"),
        section_row("S10", "Reproducibility Package", "List scripts, manifests, release checklist", "commands, smoke vs real plots, excluded caches", "Day24 checklist and Day25 plan", "Table Rep1", "artifact reproducibility with scope limits", "package hygiene"),
        section_row("S11", "Conclusion", "Conclude diagnostic benchmark contribution with explicit boundaries", "benchmark package; negative validity evidence; no method update", "Day25 claim boundary", "none", "no estimator-method conclusion", "overclaiming"),
    ]


def build_figure_table_plan(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        fig_row("F01", "figure", "Benchmark geometry overview: OC/ST/CT/RT scenes and local tunnel axes.", "configs/minibench and results/day14 artifacts", "orient readers to benchmark", "scene families and axis definitions", "real-world coverage", "Synthetic Degeneracy Benchmark", "high"),
        fig_row("F02", "figure", "Weak-direction alignment examples from whitened information spectra.", "results/day14/tables/day09_alignment_summary.csv", "show geometry diagnostic signal", "ST/CT/RT alignment and OC reliability limits", "drift prediction", "Whitened Information", "high"),
        fig_row("F03", "figure", "Legacy vs unbiased toy_lio bias audit.", "results/day30/tables/day15_bias_audit.csv and day16 summary", "show confound correction", "legacy bias and zero applied bias", "real LIO validation", "Bias Audit", "high"),
        fig_row("T01", "table", "Day17 unbiased trial summary across sequences.", "results/day30/tables/day17_unbiased_probe_summary.csv", "summarize multi-trial probe", "n_trials, zero applied bias, exploratory metrics", "metric validation", "Bias Audit", "medium"),
        fig_row("T02", "table", "Day18 within-sequence validation results.", "results/day30/tables/day18_sequence_validity_summary.csv", "show window-level stress test", "weak/undefined correlations", "robust prediction", "Metric Validity Stress Tests", "high"),
        fig_row("T03", "table", "Day19 grouped / LOSO summary.", "results/day30/tables/day19_loso_selection_results.csv", "show held-out instability", "per-sequence and LOSO results", "generalized validity", "Metric Validity Stress Tests", "high"),
        fig_row("T04", "table", "Day20 controlled partial validity.", "results/day30/tables/day20_incremental_validity_summary.csv", "show incremental validity screen", "effect sizes, expected sign, permutation status", "substantive validity if failed", "Metric Validity Stress Tests", "high"),
        fig_row("T05", "table", "Day21 joint risk comparison.", "results/day30/tables/day21_joint_risk_comparison.csv", "show no joint risk passed gate", "with-ODI and no-ODI comparison", "validated joint-risk detector", "Metric Validity Stress Tests", "medium"),
        fig_row("T06", "table", "Day22 gate decision.", "results/day30/tables/day22_gate_decision.csv", "show why method update is blocked", "method_update_authorized=false", "Go method result", "Go/No-Go Gate", "high"),
        fig_row("T07", "table", "Claim boundary table for paper writing.", "results/day30/tables/day25_claim_boundary_for_paper.csv", "prevent overclaiming", "allowed, forbidden, diagnostic-only, exploratory-only", "forbidden claims as conclusions", "Go/No-Go Gate", "high"),
        fig_row("T08", "table", "Reproducibility command table.", "results/day30/tables/day25_reproducibility_plan.csv", "make artifact executable", "commands and expected outputs", "full real-render guarantee from smoke path", "Reproducibility Package", "high"),
    ]


def build_experiment_storyline(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        story_row("E01", "Can synthetic tunnel-like geometry expose degeneracy?", "minibench and information spectrum analysis", "Day14/Day9 artifacts", "weak direction and spectrum concentration are diagnosable", "start from geometry diagnosis", "audit drift evidence", "diagnostic geometry claim allowed"),
        story_row("E02", "Is legacy drift evidence confounded?", "Day15 bias audit", "results/day30/tables/day15_bias_audit.csv", "legacy scene-family axis bias exists", "legacy toy_lio is diagnostic only", "build unbiased protocol", "bias-audit claim allowed"),
        story_row("E03", "Can we remove scene-family bias from the probe?", "Day16 unbiased protocol", "day16 summary and manifest", "applied_axis_bias is zero under none mode", "unbiased synthetic protocol established", "run multi-trial probe", "protocol claim allowed"),
        story_row("E04", "Do ODI and baselines correlate under unbiased trials?", "Day17 exploratory probe", "day17 trials and correlation tables", "merged evidence remains exploratory", "merged-only evidence can mislead", "perform window-level validation", "exploratory only"),
        story_row("E05", "Do metrics work within each sequence?", "Day18 window-level validation", "day18 window/correlation tables", "weak and undefined cases remain", "do not hide negative results", "run grouped/LOSO", "stress-test claim allowed"),
        story_row("E06", "Do metrics generalize across held-out groups?", "Day19 grouped / LOSO", "day19 tables", "stability is not sufficient for method claims", "single metrics remain exploratory", "control for baselines", "negative evidence allowed"),
        story_row("E07", "Does ODI add controlled incremental value?", "Day20 partial validity", "day20 incremental validity summary", "ODI does not pass strict controlled screen", "do not authorize control logic", "test joint risk", "negative evidence allowed"),
        story_row("E08", "Can joint risk rescue the gate?", "Day21 joint risk screen", "day21 comparison table", "all joint features remain exploratory_not_validated", "no method gate support", "formal gate review", "exploratory only"),
        story_row("E09", "What is the honest route after No-Go?", "Day22-24 gate and consolidation", "day22/day23/day24 tables", "project pivots to diagnostic benchmark / failure-analysis", "No-Go is useful evidence", "draft paper outline", "diagnostic benchmark claim allowed"),
    ]


def build_claim_boundary_for_paper(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        claim_boundary_row("CB01", "ODI robustly predicts drift", "forbidden", "ODI remains exploratory in this benchmark.", "Do not use this robust ODI wording.", "nowhere", "title, abstract, conclusion, contribution list", "Day19-21 negative validation screens"),
        claim_boundary_row("CB02", "ODI is superior to AIS/lambda_min", "forbidden", "ODI should be reported beside AIS, lambda_min_clamped, and condition_number.", "Do not claim ODI superiority.", "comparison limitations", "abstract and conclusion", "Day10/19/20 baseline competition"),
        claim_boundary_row("CB03", "Degen-LIO estimator method is validated", "forbidden", "The package does not validate a Degen-LIO estimator method.", "Do not present an estimator method as validated.", "limitations only", "title, contribution list, conclusion", "Day22 method_update_authorized=false"),
        claim_boundary_row("CB04", "weak-subspace update is authorized", "forbidden", "Weak-subspace update remains unauthorized.", "Do not implement or claim update authorization.", "gate review only", "method section", "Day21/22 weak_update_authorized=false"),
        claim_boundary_row("CB05", "diagnostic benchmark is reproducible", "conditional", "The diagnostic benchmark package is reproducible under recorded scripts and manifests.", "Do not imply full real-world estimator validation.", "artifact and reproducibility sections", "method-validation claims", "Day13/14/24 manifests and release checklist"),
        claim_boundary_row("CB06", "legacy biased toy_lio is diagnostic only", "allowed", "Legacy biased toy_lio is useful as a bias-audit lesson only.", "Do not use legacy biased toy_lio as main metric evidence.", "bias audit and limitations", "metric validity claims", "Day15 bias audit"),
        claim_boundary_row("CB07", "negative metric-validity evidence is informative", "allowed", "Negative metric-validity evidence identifies failure modes and redesign needs.", "Do not hide negative screens or rebrand them as validation.", "discussion and failure analysis", "contribution list as metric success", "Day18-24 negative evidence chain"),
        claim_boundary_row("CB08", "joint risk features are validated predictors", "forbidden", "Joint risk features are exploratory diagnostics.", "Do not present joint risk as validated.", "future work", "results conclusion", "Day21 all features exploratory_not_validated"),
    ]


def build_reproducibility_plan(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        repro_row("R00", "python3 scripts/check_env.py", "environment manifest/status", "repository checkout", "seconds", "records commit and baseline environment"),
        repro_row("R01", "python3 -m pytest -q", "full test suite result", "repository checkout", "seconds to minutes", "must pass before release"),
        repro_row("R02", "bash scripts/reproduce_day14.sh --run", "Day14 raw/metrics/tables/figures/manifests", "configs and source tree", "minutes", "uses smoke plot/sensitivity mode for CI stability; real plots can be generated separately"),
        repro_row("R15", "python3 scripts/08_bias_audit.py", "Day15 bias audit table/manifest/report", "Day14 summaries and reports", "seconds", "legacy bias audit"),
        repro_row("R16", "python3 scripts/09_run_unbiased_toy_lio.py --config configs/toy_lio/unbiased_day16.yaml", "Day16 unbiased summary/manifest/report", "Day14 minibench and ODI inputs", "seconds", "establishes zero applied bias protocol"),
        repro_row("R17", "python3 scripts/10_unbiased_metric_probe.py --config configs/toy_lio/unbiased_day17.yaml", "Day17 trial/summary/correlation tables", "Day16 protocol and Day14 inputs", "minutes", "multi-trial exploratory evidence"),
        repro_row("R18", "python3 scripts/11_within_sequence_validation.py --config configs/validation/day18_within_sequence.yaml", "Day18 window validation tables", "Day17 raw trajectories and ODI inputs", "seconds", "within-sequence validation"),
        repro_row("R19", "python3 scripts/12_grouped_loso_validation.py --config configs/validation/day19_grouped_loso.yaml", "Day19 grouped/LOSO tables", "Day18 tables", "seconds", "generalization stress test"),
        repro_row("R20", "python3 scripts/13_controlled_partial_validity.py --config configs/validation/day20_controlled_partial.yaml", "Day20 partial/permutation tables", "Day18 and Day19 tables", "seconds", "controlled incremental validity"),
        repro_row("R21", "python3 scripts/14_joint_risk_features.py --config configs/validation/day21_joint_risk.yaml", "Day21 joint-risk tables", "Day18 and Day20 tables", "seconds", "interpretable joint risk screen"),
        repro_row("R22", "python3 scripts/15_day22_gate_review.py --config configs/validation/day22_gate_review.yaml", "Day22 gate tables/manifest/report", "Day15-21 artifacts", "seconds", "formal go/no-go gate review"),
        repro_row("R23", "python3 scripts/16_day23_route_b_pivot.py --config configs/validation/day23_route_b_pivot.yaml", "Day23 Route B tables/manifest/report", "Day18-22 artifacts", "seconds", "analysis/pivot route"),
        repro_row("R24", "python3 scripts/17_day24_diagnostic_consolidation.py --config configs/validation/day24_diagnostic_consolidation.yaml", "Day24 consolidation tables/manifest/report", "Day14-23 artifacts", "seconds", "diagnostic benchmark consolidation"),
        repro_row("R25", "python3 scripts/18_day25_paper_outline.py --config configs/validation/day25_paper_outline.yaml", "Day25 paper outline tables/manifest/report", "Day14-24 artifacts", "seconds", "paper outline and figure-table plan"),
        repro_row("R26", "release archive cleanup", "archive without .git, __pycache__, .pytest_cache", "repository tree", "seconds", "exclude .git, __pycache__, and .pytest_cache from final package"),
    ]


def build_reviewer_response_plan(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        reviewer_row("RR01", "synthetic-only", "We scope the paper as a synthetic diagnostic benchmark, not real-world validation.", "Day24 inventory and benchmark protocol", "generalization remains limited", "add real-data sanity checks only after claim scope is stable"),
        reviewer_row("RR02", "toy_lio not real LIO", "toy_lio is presented as a synthetic probe and bias-audit instrument only.", "Day15-17 audit/protocol tables", "no estimator coupling claim", "keep this in limitations and claim boundary"),
        reviewer_row("RR03", "no estimator method", "The gate review explicitly blocks method update and preserves evidence integrity.", "Day22 gate decision and Day24 claim map", "less method novelty", "position as benchmark/failure-analysis contribution"),
        reviewer_row("RR04", "ODI failed validity", "We report the failed controlled validity screen as a central negative result.", "Day20 incremental validity and Day23 taxonomy", "ODI remains exploratory", "propose metric redesign rather than overclaiming"),
        reviewer_row("RR05", "joint risk failed gate", "All joint-risk candidates are retained as exploratory_not_validated, including no-ODI comparisons.", "Day21 comparison table", "no validated detector yet", "use as redesign motivation"),
        reviewer_row("RR06", "reproducibility concern", "Commands, manifests, and output inventory are explicit.", "Day13/14/24/25 manifests and repro plan", "environment-dependent plotting is smoke-tested in CI", "document smoke vs real plot commands"),
        reviewer_row("RR07", "overclaiming concern", "The paper includes a claim boundary table and forbidden wording.", "Day22-25 claim maps", "requires disciplined writing", "use claim table during drafting and review"),
    ]


def derive_day26_recommendation(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    method_allowed = bool(artifacts["day22_manifest"].get("method_update_authorized", False))
    return [
        {
            "recommended_day": "Day 26",
            "recommended_route": "paper skeleton drafting",
            "task": "draft paper skeleton with section stubs and claim-boundary notes",
            "allowed": str(not method_allowed).lower(),
            "reason": "Day25 outlines a diagnostic benchmark / failure-analysis paper route",
            "blocking_condition": "must preserve No-Go method boundary",
        },
        {
            "recommended_day": "Day 26",
            "recommended_route": "figure/table generation plan",
            "task": "turn Day25 figure/table plan into reproducible plotting/table scripts or placeholders",
            "allowed": str(not method_allowed).lower(),
            "reason": "paper route needs concrete figure/table artifacts before prose polish",
            "blocking_condition": "do not create misleading figures or hide negative results",
        },
        {
            "recommended_day": "Day 26",
            "recommended_route": "README/release cleanup",
            "task": "write release scope, commands, exclusions, and forbidden claims",
            "allowed": "true",
            "reason": "reproducible diagnostic package needs a clean release boundary",
            "blocking_condition": "exclude .git, __pycache__, and .pytest_cache from package",
        },
        {
            "recommended_day": "Day 26",
            "recommended_route": "metric redesign review",
            "task": "review metric redesign candidates without implementing estimator update",
            "allowed": str(not method_allowed).lower(),
            "reason": "secondary route after paper skeleton planning",
            "blocking_condition": "candidates remain unvalidated until future tests",
        },
        {
            "recommended_day": "Day 26",
            "recommended_route": "weak-subspace update implementation",
            "task": "implement estimator update",
            "allowed": "false",
            "reason": "blocked by Day22/24/25 method boundary",
            "blocking_condition": "requires future method_update_authorized=true",
        },
    ]


def write_day25_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    titles: Sequence[Mapping[str, str]],
    contributions: Sequence[Mapping[str, str]],
    sections: Sequence[Mapping[str, str]],
    figures: Sequence[Mapping[str, str]],
    claims: Sequence[Mapping[str, str]],
    recommendation: Sequence[Mapping[str, str]],
    artifacts: Mapping[str, Any],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    method_update_authorized = bool(artifacts["day22_manifest"].get("method_update_authorized", False))
    weak_update_authorized = bool(artifacts["day22_manifest"].get("weak_update_authorized", False))
    route = next((row["recommended_route"] for row in recommendation if row["allowed"] == "true"), "none")
    manifest = {
        "status": "OK" if not missing and titles and contributions and sections and figures and claims else "FAILED",
        "git_commit": git_commit(),
        "source_route": "diagnostic_benchmark_failure_analysis",
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "title_candidate_count": len(titles),
        "contribution_count": len(contributions),
        "section_count": len(sections),
        "figure_table_count": len(figures),
        "claim_boundary_count": len(claims),
        "recommended_day26_route": route,
        "method_update_authorized": method_update_authorized,
        "weak_update_authorized": weak_update_authorized,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "paper outline for diagnostic benchmark / failure-analysis route; no estimator method update authorized",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def title_row(cid, title, ptype, positioning, strength, risk, recommended, reason):
    return {
        "candidate_id": cid,
        "title_candidate": title,
        "paper_type": ptype,
        "positioning": positioning,
        "strength": strength,
        "main_risk": risk,
        "recommended": str(bool(recommended)).lower(),
        "reason": reason,
    }


def contribution_row(cid, text, status, evidence, blocking, section, risk, wording):
    return {
        "contribution_id": cid,
        "contribution_text": text,
        "claim_status": status,
        "supporting_evidence": evidence,
        "blocking_evidence": blocking,
        "paper_section": section,
        "risk_level": risk,
        "allowed_wording": wording,
    }


def section_row(sid, title, goal, points, evidence, figs, boundary, risk):
    return {
        "section_id": sid,
        "section_title": title,
        "section_goal": goal,
        "key_points": points,
        "required_evidence": evidence,
        "figures_tables": figs,
        "claim_boundary": boundary,
        "writing_risk": risk,
    }


def fig_row(iid, item_type, caption, source, purpose, must_show, must_not, section, priority):
    return {
        "item_id": iid,
        "item_type": item_type,
        "proposed_caption": caption,
        "source_artifact": source,
        "purpose": purpose,
        "must_show": must_show,
        "must_not_claim": must_not,
        "paper_section": section,
        "priority": priority,
    }


def story_row(step, question, analysis, artifact, result, interpretation, next_step, claim):
    return {
        "story_step": step,
        "question": question,
        "experiment_or_analysis": analysis,
        "evidence_artifact": artifact,
        "observed_result": result,
        "interpretation": interpretation,
        "next_step": next_step,
        "claim_allowed": claim,
    }


def claim_boundary_row(cid, text, status, allowed, forbidden, use, avoid, evidence):
    return {
        "claim_id": cid,
        "claim_text": text,
        "status": status,
        "allowed_wording": allowed,
        "forbidden_wording": forbidden,
        "where_to_use": use,
        "where_to_avoid": avoid,
        "evidence_basis": evidence,
    }


def repro_row(step, command, outputs, inputs, runtime, notes):
    return {
        "repro_step": step,
        "command": command,
        "expected_outputs": outputs,
        "required_inputs": inputs,
        "runtime_expectation": runtime,
        "notes": notes,
    }


def reviewer_row(rid, attack, response, evidence, limitation, mitigation):
    return {
        "risk_id": rid,
        "reviewer_attack": attack,
        "short_response": response,
        "evidence_to_cite": evidence,
        "remaining_limitation": limitation,
        "planned_mitigation": mitigation,
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
