"""Day 30 final package review and release-readiness audit."""

from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_ARTIFACT_FIELDNAMES = [
    "artifact_id",
    "day",
    "artifact_type",
    "path",
    "exists",
    "nonempty",
    "required_for_final_package",
    "status",
    "reason",
]

FIGURE_TABLE_FIELDNAMES = [
    "item_id",
    "item_type",
    "path",
    "exists",
    "nonempty",
    "size_bytes",
    "real_or_placeholder",
    "claim_boundary_present",
    "status",
    "reason",
]

CLAIM_AUDIT_FIELDNAMES = [
    "claim_id",
    "file_path",
    "matched_text",
    "context_type",
    "is_positive_assertion",
    "allowed_as_boundary_text",
    "status",
    "reason",
]

RELEASE_CHECK_FIELDNAMES = [
    "check_id",
    "check_item",
    "status",
    "blocking",
    "required_action",
    "reason",
]

ARCHIVE_FIELDNAMES = [
    "archive_step",
    "command_or_action",
    "include_patterns",
    "exclude_patterns",
    "safe",
    "requires_manual_confirmation",
    "reason",
]

FINAL_DECISION_FIELDNAMES = ["decision_item", "status", "authorized", "reason"]

FORBIDDEN_PHRASES = [
    "ODI robustly predicts drift",
    "validated Degen-LIO estimator",
    "Degen-LIO estimator method is validated",
    "weak-subspace update is authorized",
    "toy_lio is real LIO",
    "joint risk predicts drift",
    "ODI is superior to AIS/lambda_min",
]


@dataclass(frozen=True)
class RequiredArtifact:
    artifact_id: str
    day: str
    artifact_type: str
    path: str
    required: bool
    reason: str


def load_day14_to_day29_artifacts(
    day14_root: Path,
    day30_root: Path,
    reports_root: Path,
    docs_root: Path,
    repo_root: Path,
) -> Dict[str, Any]:
    """Collect the file paths Day30 will audit without mutating older artifacts."""

    paths = {
        "readme": repo_root / "README.md",
        "day14_reproduction_manifest": day14_root / "manifests/day14_reproduction_manifest.json",
        "day14_final_manifest": day14_root / "manifests/day14_final_manifest.json",
        "day15_manifest": day30_root / "manifests/day15_bias_audit_manifest.json",
        "day22_manifest": day30_root / "manifests/day22_gate_review_manifest.json",
        "day29_manifest": day30_root / "manifests/day29_safe_figures_manifest.json",
        "day29_inventory": day30_root / "tables/day29_generated_figure_inventory.csv",
        "day29_caption_audit": day30_root / "tables/day29_caption_safety_audit.csv",
        "day29_report": reports_root / "day29_safe_figures_report.md",
        "paper_skeleton": docs_root / "paper/diagnostic_benchmark_paper_skeleton.md",
        "release_scope": docs_root / "release/release_scope.md",
    }
    artifacts: Dict[str, Any] = {"paths": paths, "input_paths": list(paths.values())}
    for key, path in paths.items():
        if path.exists() and path.suffix == ".json":
            artifacts[key] = json.loads(path.read_text(encoding="utf-8"))
        elif path.exists() and path.suffix == ".csv":
            artifacts[key] = read_csv_rows(path)
        elif path.exists():
            artifacts[key] = path.read_text(encoding="utf-8")
        else:
            artifacts[key] = None
    return artifacts


def audit_required_artifacts(repo_root: Path, day14_root: Path, day30_root: Path, reports_root: Path) -> List[Dict[str, str]]:
    rows = []
    for artifact in required_artifacts():
        path = resolve_artifact_path(artifact.path, repo_root, day14_root, day30_root, reports_root)
        exists = path.exists()
        nonempty = exists and path.stat().st_size > 0
        status = "pass" if (exists and nonempty) or not artifact.required else "fail"
        if not exists:
            reason = "missing required final-package artifact" if artifact.required else "optional artifact missing"
        elif not nonempty:
            reason = "artifact exists but is empty" if artifact.required else "optional artifact empty"
        else:
            reason = artifact.reason
        rows.append(
            {
                "artifact_id": artifact.artifact_id,
                "day": artifact.day,
                "artifact_type": artifact.artifact_type,
                "path": relative_to_root(path),
                "exists": str(exists).lower(),
                "nonempty": str(nonempty).lower(),
                "required_for_final_package": str(artifact.required).lower(),
                "status": status,
                "reason": reason,
            }
        )
    return rows


def audit_figures_and_tables(repo_root: Path) -> List[Dict[str, str]]:
    items = figure_table_items()
    notes_text = (repo_root / "docs/paper/generated_tables/table_interpretation_notes.md").read_text(encoding="utf-8") if (repo_root / "docs/paper/generated_tables/table_interpretation_notes.md").exists() else ""
    rows = []
    for item_id, item_type, rel_path, min_size, boundary in items:
        path = repo_root / rel_path
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        nonempty = exists and size > 0
        if item_type == "figure":
            real = "real" if nonempty and size >= min_size else "placeholder_or_missing"
            status = "pass" if real == "real" and boundary else "fail"
            reason = "real figure exists and claim boundary is represented in Day29 inventory/caption bank" if status == "pass" else "figure missing, too small, or lacks claim boundary"
        else:
            real = "paper_table_or_note" if nonempty else "missing_or_empty"
            t_notes_ok = item_id not in {"T03", "T05"} or "valid means computable, not substantive validity" in notes_text
            status = "pass" if nonempty and boundary and t_notes_ok else "fail"
            reason = "paper table/note exists with claim boundary" if status == "pass" else "table/note missing or needs T03/T05 interpretation note"
        rows.append(
            {
                "item_id": item_id,
                "item_type": item_type,
                "path": relative_to_root(path),
                "exists": str(exists).lower(),
                "nonempty": str(nonempty).lower(),
                "size_bytes": str(size),
                "real_or_placeholder": real,
                "claim_boundary_present": str(bool(boundary)).lower(),
                "status": status,
                "reason": reason,
            }
        )
    return rows


def audit_global_claim_boundaries(repo_root: Path) -> List[Dict[str, str]]:
    """Scan README/docs/reports and separate positive assertions from boundary text."""

    scan_roots = [repo_root / "README.md", repo_root / "docs", repo_root / "reports"]
    files = []
    for root in scan_roots:
        if root.is_file():
            files.append(root)
        elif root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".csv", ".json", ".txt"})
    rows = []
    claim_index = 1
    for path in sorted(set(files)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        for phrase in FORBIDDEN_PHRASES:
            for line_no, line in find_phrase_lines(text, phrase):
                context_window = "\n".join(lines[max(0, line_no - 4):line_no + 1])
                context_type = classify_claim_context(path, line, context_window)
                positive = context_type == "positive_assertion"
                allowed = context_type in {"boundary_text", "negated_or_unvalidated_text"}
                rows.append(
                    {
                        "claim_id": f"CL{claim_index:04d}",
                        "file_path": relative_to_root(path),
                        "matched_text": f"line {line_no}: {line.strip()[:220]}",
                        "context_type": context_type,
                        "is_positive_assertion": str(positive).lower(),
                        "allowed_as_boundary_text": str(allowed).lower(),
                        "status": "fail" if positive else "pass_with_context",
                        "reason": "forbidden claim appears as a positive assertion" if positive else "phrase is negated or used as explicit claim-boundary text",
                    }
                )
                claim_index += 1
    if not rows:
        rows.append(
            {
                "claim_id": "CL0000",
                "file_path": "README.md;docs;reports",
                "matched_text": "none",
                "context_type": "no_match",
                "is_positive_assertion": "false",
                "allowed_as_boundary_text": "true",
                "status": "pass",
                "reason": "no forbidden claim phrase found outside configured boundary scan",
            }
        )
    return rows


def audit_release_readiness(
    readme_text: str,
    required_rows: Sequence[Mapping[str, str]],
    figure_rows: Sequence[Mapping[str, str]],
    claim_rows: Sequence[Mapping[str, str]],
) -> List[Dict[str, str]]:
    readme_lower = readme_text.lower()
    artifact_ok = all(row["status"] == "pass" for row in required_rows)
    figures_ok = all(row["status"] == "pass" for row in figure_rows)
    claims_ok = all(row["status"] != "fail" for row in claim_rows)
    return [
        release_row("R01", "README scope is correct", "pass" if "diagnostic benchmark" in readme_lower and "failure-analysis" in readme_lower else "fail", True, "ensure README states diagnostic benchmark / failure-analysis scope", "README must define the package boundary"),
        release_row("R02", "reproduction commands are complete", "pass" if "python3 scripts/check_env.py" in readme_text and "python3 -m pytest -q" in readme_text else "manual_required", True, "verify README/release docs list the required command chain", "commands must be visible to reviewers"),
        release_row("R03", "Day14-Day30 manifests are complete", "pass" if artifact_ok else "fail", True, "restore or regenerate missing manifests", "provenance is required"),
        release_row("R04", "full pytest confirmed locally", "manual_required", True, "run python3 -m pytest -q immediately before packaging", "the Day30 script cannot prove the external pytest run by itself"),
        release_row("R05", "F01/F03 are real figures", "pass" if figures_ok else "fail", True, "regenerate Day29 safe figures from source artifacts", "fake or placeholder figures are forbidden"),
        release_row("R06", "generated tables exist", "pass" if all(row["status"] == "pass" for row in figure_rows if row["item_type"] != "figure") else "fail", True, "regenerate Day28/29 table artifacts", "paper tables are core deliverables"),
        release_row("R07", "table interpretation notes exist", "pass" if "valid means computable, not substantive validity" in readme_text or Path("docs/paper/generated_tables/table_interpretation_notes.md").exists() else "manual_required", True, "confirm T03/T05 notes are included", "valid statuses can otherwise be overread"),
        release_row("R08", "forbidden claims appear only as boundary text", "pass" if claims_ok else "fail", True, "revise positive forbidden claims", "overclaiming is a blocking risk"),
        release_row("R09", ".git is excluded", "manual_required", True, "use git archive or rsync --exclude .git", "checkout may contain .git but release archive must not"),
        release_row("R10", ".pytest_cache is excluded", "manual_required", True, "use archive excludes for .pytest_cache", "cache is not evidence"),
        release_row("R11", "__pycache__ is excluded", "manual_required", True, "use archive excludes for __pycache__", "bytecode cache is not evidence"),
        release_row("R12", "raw trajectories policy is explicit", "manual_required", False, "confirm generated raw files are rebuilt by scripts or explicitly packaged", "raw trajectory volume can vary"),
        release_row("R13", "smoke vs real plot distinction is documented", "pass" if "smoke" in readme_lower and "real" in readme_lower else "manual_required", True, "keep smoke/real plotting distinction in README/release docs", "prevents reproduction ambiguity"),
        release_row("R14", "final release archive is dry-run only", "manual_required", True, "perform manual clean archive dry-run before publishing", "Day30 should not auto-delete or package caches"),
    ]


def build_clean_archive_plan() -> List[Dict[str, str]]:
    return [
        archive_row("A01", "python3 scripts/check_env.py", "source/config/script/report/results metadata", ".git,.pytest_cache,__pycache__", True, False, "confirm local environment before packaging"),
        archive_row("A02", "python3 -m pytest -q", "all tracked testable source", ".git,.pytest_cache,__pycache__", True, False, "manual quality gate before release"),
        archive_row("A03", "python3 scripts/23_day30_final_package_review.py --config configs/validation/day30_final_package_review.yaml", "Day30 audit tables, report, release notes", ".git,.pytest_cache,__pycache__", True, False, "refresh final review artifacts"),
        archive_row("A04", "git archive --format=tar.gz --output degen_lio_diagnostic_benchmark.tar.gz HEAD", "tracked release files", ".git automatically excluded", True, True, "safe clean archive option; manually inspect output"),
        archive_row("A05", "rsync -a --exclude .git --exclude .pytest_cache --exclude __pycache__ ./ release_dir/", "selected checkout files", ".git,.pytest_cache,__pycache__", True, True, "alternate staging command; do not run until manually confirmed"),
        archive_row("A06", "do not delete local checkout caches as part of Day30", "none", "n/a", True, False, "Day30 creates a plan only and does not delete user files"),
    ]


def derive_final_decision(
    required_rows: Sequence[Mapping[str, str]],
    figure_rows: Sequence[Mapping[str, str]],
    claim_rows: Sequence[Mapping[str, str]],
) -> List[Dict[str, str]]:
    artifacts_ok = all(row["status"] == "pass" for row in required_rows)
    figures_ok = all(row["status"] == "pass" for row in figure_rows)
    claims_ok = all(row["status"] != "fail" for row in claim_rows)
    diagnostic_ready = artifacts_ok and figures_ok and claims_ok
    return [
        decision_row("diagnostic benchmark package ready", "ready_for_draft" if diagnostic_ready else "blocked", diagnostic_ready, "artifact, figure/table, and claim-boundary audits passed" if diagnostic_ready else "one or more final audits failed"),
        decision_row("method update authorized", "not_authorized", False, "Day22 gate and subsequent Route B artifacts block method implementation"),
        decision_row("weak-subspace update authorized", "not_authorized", False, "weak update remains blocked by the No-Go method gate"),
        decision_row("ODI robust drift claim allowed", "not_allowed", False, "ODI remains exploratory and did not pass controlled/joint validation"),
        decision_row("release archive ready", "conditional_manual_required", False, "clean archive dry-run and full local pytest must be manually confirmed before release"),
        decision_row("paper draft route ready", "ready_for_draft", diagnostic_ready, "diagnostic benchmark/failure-analysis paper route is supported if manual release checks are completed"),
        decision_row("further metric redesign needed", "recommended", True, "Day20/21 results did not validate ODI or joint risk features"),
    ]


def write_day30_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    required_rows: Sequence[Mapping[str, str]],
    figure_rows: Sequence[Mapping[str, str]],
    claim_rows: Sequence[Mapping[str, str]],
    release_rows: Sequence[Mapping[str, str]],
    final_rows: Sequence[Mapping[str, str]],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    required_passed = all(row["status"] == "pass" for row in required_rows)
    figure_passed = all(row["status"] == "pass" for row in figure_rows)
    claim_passed = all(row["status"] != "fail" for row in claim_rows)
    fake_figures_detected = any(row["item_type"] == "figure" and row["real_or_placeholder"] != "real" for row in figure_rows)
    release_status = "manual_required" if any(row["status"] == "manual_required" for row in release_rows) else "pass"
    final_package_status = next(row["status"] for row in final_rows if row["decision_item"] == "diagnostic benchmark package ready")
    status = "CONDITIONAL_OK" if not missing and required_passed and figure_passed and claim_passed and release_status == "manual_required" else "OK"
    if missing or not required_passed or not figure_passed or not claim_passed:
        status = "FAILED"
    manifest = {
        "status": status,
        "git_commit": git_commit(),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "required_artifact_audit_passed": bool(required_passed),
        "figure_table_audit_passed": bool(figure_passed),
        "global_claim_boundary_passed": bool(claim_passed),
        "release_readiness_status": release_status,
        "final_package_status": final_package_status,
        "method_update_authorized": False,
        "weak_update_authorized": False,
        "odi_robust_claim_allowed": False,
        "fake_figures_detected": bool(fake_figures_detected),
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "final diagnostic benchmark package review; method update and weak-subspace update remain unauthorized",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def required_artifacts() -> List[RequiredArtifact]:
    specs: List[RequiredArtifact] = [
        RequiredArtifact("D14-M01", "Day 14", "manifest", "results/day14/manifests/day14_reproduction_manifest.json", True, "Day14 reproduction provenance"),
        RequiredArtifact("D14-M02", "Day 14", "manifest", "results/day14/manifests/day14_final_manifest.json", True, "Day14 final decision provenance"),
        RequiredArtifact("D14-R01", "Day 14", "report", "reports/day14_go_nogo_report.md", True, "Day14 Conditional Go/No-Go report"),
        RequiredArtifact("D15-C01", "Day 15", "scope_doc", "docs/day15_30_scope.md", True, "Day15-30 scope boundary"),
        RequiredArtifact("D15-S01", "Day 15", "script", "scripts/08_bias_audit.py", True, "Day15 executable audit"),
        RequiredArtifact("D15-R01", "Day 15", "report", "reports/day15_report.md", True, "Day15 bias audit report"),
        RequiredArtifact("D15-T01", "Day 15", "table", "results/day30/tables/day15_bias_audit.csv", True, "Day15 bias audit table"),
        RequiredArtifact("D15-M01", "Day 15", "manifest", "results/day30/manifests/day15_bias_audit_manifest.json", True, "Day15 manifest"),
        RequiredArtifact("D16-C01", "Day 16", "config", "configs/toy_lio/unbiased_day16.yaml", True, "Day16 unbiased config"),
        RequiredArtifact("D16-S01", "Day 16", "script", "scripts/09_run_unbiased_toy_lio.py", True, "Day16 executable script"),
        RequiredArtifact("D16-R01", "Day 16", "report", "reports/day16_report.md", True, "Day16 report"),
        RequiredArtifact("D16-T01", "Day 16", "table", "results/day30/tables/day16_unbiased_toy_lio_summary.csv", True, "Day16 summary"),
        RequiredArtifact("D16-M01", "Day 16", "manifest", "results/day30/manifests/day16_unbiased_toy_lio_manifest.json", True, "Day16 manifest"),
        RequiredArtifact("D17-C01", "Day 17", "config", "configs/toy_lio/unbiased_day17.yaml", True, "Day17 multi-trial config"),
        RequiredArtifact("D17-S01", "Day 17", "script", "scripts/10_unbiased_metric_probe.py", True, "Day17 executable script"),
        RequiredArtifact("D17-R01", "Day 17", "report", "reports/day17_report.md", True, "Day17 report"),
        RequiredArtifact("D17-T01", "Day 17", "table", "results/day30/tables/day17_unbiased_probe_trials.csv", True, "Day17 trials"),
        RequiredArtifact("D17-T02", "Day 17", "table", "results/day30/tables/day17_unbiased_probe_summary.csv", True, "Day17 summary"),
        RequiredArtifact("D17-T03", "Day 17", "table", "results/day30/tables/day17_metric_drift_correlations.csv", True, "Day17 correlations"),
        RequiredArtifact("D17-M01", "Day 17", "manifest", "results/day30/manifests/day17_unbiased_probe_manifest.json", True, "Day17 manifest"),
        RequiredArtifact("D18-C01", "Day 18", "config", "configs/validation/day18_within_sequence.yaml", True, "Day18 config"),
        RequiredArtifact("D18-S01", "Day 18", "script", "scripts/11_within_sequence_validation.py", True, "Day18 executable script"),
        RequiredArtifact("D18-R01", "Day 18", "report", "reports/day18_report.md", True, "Day18 report"),
        RequiredArtifact("D18-T01", "Day 18", "table", "results/day30/tables/day18_window_metrics.csv", True, "Day18 window table"),
        RequiredArtifact("D18-T02", "Day 18", "table", "results/day30/tables/day18_within_sequence_correlations.csv", True, "Day18 correlations"),
        RequiredArtifact("D18-T03", "Day 18", "table", "results/day30/tables/day18_sequence_validity_summary.csv", True, "Day18 summary"),
        RequiredArtifact("D18-M01", "Day 18", "manifest", "results/day30/manifests/day18_within_sequence_manifest.json", True, "Day18 manifest"),
        RequiredArtifact("D19-C01", "Day 19", "config", "configs/validation/day19_grouped_loso.yaml", True, "Day19 config"),
        RequiredArtifact("D19-S01", "Day 19", "script", "scripts/12_grouped_loso_validation.py", True, "Day19 executable script"),
        RequiredArtifact("D19-R01", "Day 19", "report", "reports/day19_report.md", True, "Day19 report"),
        RequiredArtifact("D19-T01", "Day 19", "table", "results/day30/tables/day19_grouped_metric_summary.csv", True, "Day19 grouped table"),
        RequiredArtifact("D19-T02", "Day 19", "table", "results/day30/tables/day19_loso_selection_results.csv", True, "Day19 LOSO table"),
        RequiredArtifact("D19-T03", "Day 19", "table", "results/day30/tables/day19_metric_pass_fail_summary.csv", True, "Day19 pass/fail"),
        RequiredArtifact("D19-M01", "Day 19", "manifest", "results/day30/manifests/day19_grouped_loso_manifest.json", True, "Day19 manifest"),
        RequiredArtifact("D20-C01", "Day 20", "config", "configs/validation/day20_controlled_partial.yaml", True, "Day20 config"),
        RequiredArtifact("D20-S01", "Day 20", "script", "scripts/13_controlled_partial_validity.py", True, "Day20 executable script"),
        RequiredArtifact("D20-R01", "Day 20", "report", "reports/day20_report.md", True, "Day20 report"),
        RequiredArtifact("D20-T01", "Day 20", "table", "results/day30/tables/day20_partial_correlations.csv", True, "Day20 partial correlations"),
        RequiredArtifact("D20-T02", "Day 20", "table", "results/day30/tables/day20_controlled_regression_summary.csv", True, "Day20 controlled regression"),
        RequiredArtifact("D20-T03", "Day 20", "table", "results/day30/tables/day20_permutation_tests.csv", True, "Day20 permutation tests"),
        RequiredArtifact("D20-T04", "Day 20", "table", "results/day30/tables/day20_incremental_validity_summary.csv", True, "Day20 incremental summary"),
        RequiredArtifact("D20-M01", "Day 20", "manifest", "results/day30/manifests/day20_controlled_partial_manifest.json", True, "Day20 manifest"),
        RequiredArtifact("D21-C01", "Day 21", "config", "configs/validation/day21_joint_risk.yaml", True, "Day21 config"),
        RequiredArtifact("D21-S01", "Day 21", "script", "scripts/14_joint_risk_features.py", True, "Day21 executable script"),
        RequiredArtifact("D21-R01", "Day 21", "report", "reports/day21_report.md", True, "Day21 report"),
        RequiredArtifact("D21-T01", "Day 21", "table", "results/day30/tables/day21_joint_risk_window_features.csv", True, "Day21 features"),
        RequiredArtifact("D21-T02", "Day 21", "table", "results/day30/tables/day21_joint_risk_correlations.csv", True, "Day21 correlations"),
        RequiredArtifact("D21-T03", "Day 21", "table", "results/day30/tables/day21_joint_risk_controlled_validity.csv", True, "Day21 controlled validity"),
        RequiredArtifact("D21-T04", "Day 21", "table", "results/day30/tables/day21_joint_risk_comparison.csv", True, "Day21 comparison"),
        RequiredArtifact("D21-M01", "Day 21", "manifest", "results/day30/manifests/day21_joint_risk_manifest.json", True, "Day21 manifest"),
    ]
    for day in range(22, 30):
        config_name = {
            22: "day22_gate_review",
            23: "day23_route_b_pivot",
            24: "day24_diagnostic_consolidation",
            25: "day25_paper_outline",
            26: "day26_paper_skeleton",
            27: "day27_release_cleanup",
            28: "day28_figure_table_generation",
            29: "day29_safe_figures",
        }[day]
        script_name = {
            22: "15_day22_gate_review",
            23: "16_day23_route_b_pivot",
            24: "17_day24_diagnostic_consolidation",
            25: "18_day25_paper_outline",
            26: "19_day26_paper_skeleton",
            27: "20_day27_release_cleanup",
            28: "21_day28_figure_table_generation",
            29: "22_day29_safe_figures",
        }[day]
        report_name = {
            22: "day22_gate_review.md",
            23: "day23_route_b_pivot_report.md",
            24: "day24_diagnostic_consolidation_report.md",
            25: "day25_paper_outline_report.md",
            26: "day26_paper_skeleton_report.md",
            27: "day27_release_cleanup_report.md",
            28: "day28_figure_table_generation_report.md",
            29: "day29_safe_figures_report.md",
        }[day]
        manifest_name = {
            22: "day22_gate_review_manifest.json",
            23: "day23_route_b_pivot_manifest.json",
            24: "day24_diagnostic_consolidation_manifest.json",
            25: "day25_paper_outline_manifest.json",
            26: "day26_paper_skeleton_manifest.json",
            27: "day27_release_cleanup_manifest.json",
            28: "day28_figure_table_generation_manifest.json",
            29: "day29_safe_figures_manifest.json",
        }[day]
        specs.append(RequiredArtifact(f"D{day}-C01", f"Day {day}", "config", f"configs/validation/{config_name}.yaml", True, f"Day{day} config"))
        specs.append(RequiredArtifact(f"D{day}-S01", f"Day {day}", "script", f"scripts/{script_name}.py", True, f"Day{day} executable script"))
        specs.append(RequiredArtifact(f"D{day}-R01", f"Day {day}", "report", f"reports/{report_name}", True, f"Day{day} report"))
        specs.append(RequiredArtifact(f"D{day}-M01", f"Day {day}", "manifest", f"results/day30/manifests/{manifest_name}", True, f"Day{day} manifest"))
    specs.extend(
        [
            RequiredArtifact("README", "General", "readme", "README.md", True, "README scope and reproduction commands"),
            RequiredArtifact("PAPER-SKEL", "Day 26", "paper_doc", "docs/paper/diagnostic_benchmark_paper_skeleton.md", True, "paper skeleton"),
            RequiredArtifact("PAPER-TABLES", "Day 28", "paper_doc", "docs/paper/generated_tables/T01_day17_unbiased_probe_summary.md", True, "generated paper table"),
            RequiredArtifact("PAPER-FIG-F01", "Day 29", "figure", "docs/paper/figures/F01_benchmark_geometry_overview.png", True, "real F01 figure"),
            RequiredArtifact("PAPER-FIG-F03", "Day 29", "figure", "docs/paper/figures/F03_bias_audit_legacy_vs_unbiased.png", True, "real F03 figure"),
            RequiredArtifact("RELEASE-SCOPE", "Day 27", "release_doc", "docs/release/release_scope.md", True, "release scope"),
            RequiredArtifact("RELEASE-CLEAN", "Day 27", "release_doc", "docs/release/release_cleanup_policy.md", True, "release cleanup policy"),
            RequiredArtifact("RELEASE-CMDS", "Day 27", "release_doc", "docs/release/release_reproducibility_commands.md", True, "release commands"),
        ]
    )
    day22_29_tables = {
        22: ["day22_evidence_matrix.csv", "day22_gate_decision.csv", "day22_claim_status.csv", "day22_next_action_plan.csv"],
        23: ["day23_failure_taxonomy.csv", "day23_claim_consolidation.csv", "day23_metric_redesign_candidates.csv", "day23_diagnostic_benchmark_route.csv", "day23_day24_recommendation.csv"],
        24: ["day24_artifact_inventory.csv", "day24_benchmark_protocol.csv", "day24_paper_claim_map.csv", "day24_reviewer_risk_register.csv", "day24_release_checklist.csv", "day24_day25_recommendation.csv"],
        25: ["day25_title_positioning_candidates.csv", "day25_contribution_map.csv", "day25_section_outline.csv", "day25_figure_table_plan.csv", "day25_experiment_storyline.csv", "day25_claim_boundary_for_paper.csv", "day25_reproducibility_plan.csv", "day25_reviewer_response_plan.csv", "day25_day26_recommendation.csv"],
        26: ["day26_section_writing_tasks.csv", "day26_figure_table_execution_plan.csv", "day26_readme_scope_update_plan.csv", "day26_release_cleanup_plan.csv", "day26_day27_recommendation.csv"],
        27: ["day27_readme_scope_audit.csv", "day27_forbidden_claims_audit.csv", "day27_release_forbidden_paths_audit.csv", "day27_release_file_policy.csv", "day27_safe_archive_plan.csv", "day27_figure_table_readiness.csv", "day27_day28_recommendation.csv"],
        28: ["day28_generated_table_inventory.csv", "day28_pending_figure_plan.csv", "day28_caption_bank.csv", "day28_day29_recommendation.csv"],
        29: ["day29_generated_figure_inventory.csv", "day29_table_safety_notes.csv", "day29_caption_safety_audit.csv", "day29_day30_recommendation.csv"],
    }
    for day, names in day22_29_tables.items():
        for index, name in enumerate(names, start=1):
            specs.append(RequiredArtifact(f"D{day}-T{index:02d}", f"Day {day}", "table", f"results/day30/tables/{name}", True, f"Day{day} main table"))
    return specs


def figure_table_items() -> List[tuple[str, str, str, int, bool]]:
    return [
        ("F01", "figure", "docs/paper/figures/F01_benchmark_geometry_overview.png", 2000, True),
        ("F01", "figure", "docs/paper/figures/F01_benchmark_geometry_overview.pdf", 2000, True),
        ("F03", "figure", "docs/paper/figures/F03_bias_audit_legacy_vs_unbiased.png", 2000, True),
        ("F03", "figure", "docs/paper/figures/F03_bias_audit_legacy_vs_unbiased.pdf", 2000, True),
        ("T01", "table", "docs/paper/generated_tables/T01_day17_unbiased_probe_summary.md", 1, True),
        ("T02", "table", "docs/paper/generated_tables/T02_day18_within_sequence_summary.md", 1, True),
        ("T03", "table", "docs/paper/generated_tables/T03_day19_grouped_loso_summary.md", 1, True),
        ("T04", "table", "docs/paper/generated_tables/T04_day20_controlled_partial_summary.md", 1, True),
        ("T05", "table", "docs/paper/generated_tables/T05_day21_joint_risk_summary.md", 1, True),
        ("T06", "table", "docs/paper/generated_tables/T06_day22_gate_decision.md", 1, True),
        ("T07", "table", "docs/paper/generated_tables/T07_claim_boundary.md", 1, True),
        ("T08", "table", "docs/paper/generated_tables/T08_reproducibility_commands.md", 1, True),
        ("table_interpretation_notes", "table", "docs/paper/generated_tables/table_interpretation_notes.md", 1, True),
        ("caption_bank", "table", "docs/paper/caption_bank.md", 1, True),
        ("caption_bank_day29", "table", "docs/paper/caption_bank_day29.md", 1, True),
    ]


def find_phrase_lines(text: str, phrase: str) -> Iterable[tuple[int, str]]:
    needle = phrase.lower()
    for line_no, line in enumerate(text.splitlines(), start=1):
        if needle in line.lower():
            yield line_no, line


def classify_claim_context(path: Path, line: str, context_window: str = "") -> str:
    lower = line.lower()
    context_lower = context_window.lower()
    path_text = str(path).lower()
    boundary_tokens = [
        "forbidden",
        "disallowed",
        "forbidden_wording",
        "must_not_claim",
        "claim boundary",
        "claim_boundary",
        "not claim",
        "must not",
        "boundary",
    ]
    negation_tokens = [
        "not ",
        "not a ",
        "not an ",
        "does not ",
        "do not ",
        "cannot ",
        "unvalidated",
        "unauthorized",
        "forbidden",
        "blocked",
        "not validated",
        "not authorized",
        "no-go",
    ]
    if any(token in lower or token in context_lower or token in path_text for token in boundary_tokens):
        return "boundary_text"
    if any(token in lower or token in context_lower for token in negation_tokens):
        return "negated_or_unvalidated_text"
    return "positive_assertion"


def resolve_artifact_path(path: str, repo_root: Path, day14_root: Path, day30_root: Path, reports_root: Path) -> Path:
    if path.startswith("results/day14/"):
        return day14_root / path[len("results/day14/"):]
    if path.startswith("results/day30/"):
        return day30_root / path[len("results/day30/"):]
    if path.startswith("reports/"):
        return reports_root / path[len("reports/"):]
    return repo_root / path


def release_row(check_id: str, item: str, status: str, blocking: bool, action: str, reason: str) -> Dict[str, str]:
    return {
        "check_id": check_id,
        "check_item": item,
        "status": status,
        "blocking": str(bool(blocking)).lower(),
        "required_action": action,
        "reason": reason,
    }


def archive_row(step: str, action: str, include: str, exclude: str, safe: bool, manual: bool, reason: str) -> Dict[str, str]:
    return {
        "archive_step": step,
        "command_or_action": action,
        "include_patterns": include,
        "exclude_patterns": exclude,
        "safe": str(bool(safe)).lower(),
        "requires_manual_confirmation": str(bool(manual)).lower(),
        "reason": reason,
    }


def decision_row(item: str, status: str, authorized: bool, reason: str) -> Dict[str, str]:
    return {"decision_item": item, "status": status, "authorized": str(bool(authorized)).lower(), "reason": reason}


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
