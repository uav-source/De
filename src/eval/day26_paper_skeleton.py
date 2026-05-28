"""Day 26 paper skeleton and release-plan generation."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

SECTION_TASK_FIELDNAMES = [
    "section_id",
    "section_title",
    "writing_task",
    "source_evidence",
    "required_figures_tables",
    "allowed_claims",
    "forbidden_claims",
    "priority",
    "owner_note",
]

FIGURE_EXEC_FIELDNAMES = [
    "item_id",
    "item_type",
    "source_artifact",
    "output_target",
    "generation_status",
    "needed_script_or_manual_action",
    "caption_draft",
    "must_show",
    "must_not_claim",
    "priority",
]

README_FIELDNAMES = [
    "readme_section",
    "required_update",
    "reason",
    "allowed_wording",
    "forbidden_wording",
    "blocking",
]

RELEASE_FIELDNAMES = [
    "cleanup_item",
    "path_or_pattern",
    "current_status",
    "required_action",
    "blocking_for_release",
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


def load_day14_to_day25_artifacts(day14_root: Path, day30_root: Path, reports_root: Path) -> Dict[str, Any]:
    """Load Day 14-25 artifacts used to create a paper skeleton."""

    paths = {
        "day14_reproduction_manifest": day14_root / "manifests/day14_reproduction_manifest.json",
        "day14_final_manifest": day14_root / "manifests/day14_final_manifest.json",
        "day14_report": reports_root / "day14_go_nogo_report.md",
        "day15_manifest": day30_root / "manifests/day15_bias_audit_manifest.json",
        "day15_report": reports_root / "day15_report.md",
        "day16_manifest": day30_root / "manifests/day16_unbiased_toy_lio_manifest.json",
        "day16_report": reports_root / "day16_report.md",
        "day17_manifest": day30_root / "manifests/day17_unbiased_probe_manifest.json",
        "day17_report": reports_root / "day17_report.md",
        "day18_manifest": day30_root / "manifests/day18_within_sequence_manifest.json",
        "day18_report": reports_root / "day18_report.md",
        "day19_manifest": day30_root / "manifests/day19_grouped_loso_manifest.json",
        "day19_report": reports_root / "day19_report.md",
        "day20_manifest": day30_root / "manifests/day20_controlled_partial_manifest.json",
        "day20_report": reports_root / "day20_report.md",
        "day21_manifest": day30_root / "manifests/day21_joint_risk_manifest.json",
        "day21_report": reports_root / "day21_report.md",
        "day22_manifest": day30_root / "manifests/day22_gate_review_manifest.json",
        "day22_report": reports_root / "day22_gate_review.md",
        "day23_manifest": day30_root / "manifests/day23_route_b_pivot_manifest.json",
        "day23_report": reports_root / "day23_route_b_pivot_report.md",
        "day24_manifest": day30_root / "manifests/day24_diagnostic_consolidation_manifest.json",
        "day24_report": reports_root / "day24_diagnostic_consolidation_report.md",
        "day25_titles": day30_root / "tables/day25_title_positioning_candidates.csv",
        "day25_contributions": day30_root / "tables/day25_contribution_map.csv",
        "day25_sections": day30_root / "tables/day25_section_outline.csv",
        "day25_figures": day30_root / "tables/day25_figure_table_plan.csv",
        "day25_storyline": day30_root / "tables/day25_experiment_storyline.csv",
        "day25_claims": day30_root / "tables/day25_claim_boundary_for_paper.csv",
        "day25_repro": day30_root / "tables/day25_reproducibility_plan.csv",
        "day25_reviewer": day30_root / "tables/day25_reviewer_response_plan.csv",
        "day25_recommendation": day30_root / "tables/day25_day26_recommendation.csv",
        "day25_manifest": day30_root / "manifests/day25_paper_outline_manifest.json",
        "day25_report": reports_root / "day25_paper_outline_report.md",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day26 input file(s): "
            + "; ".join(missing)
            + ". Run Day 14-25 scripts before Day 26 paper skeleton generation."
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


def build_paper_skeleton_markdown(artifacts: Mapping[str, Any]) -> str:
    """Build an editable markdown skeleton for the diagnostic benchmark paper."""

    titles = artifacts["day25_titles"]
    sections = artifacts["day25_sections"]
    claims = artifacts["day25_claims"]
    figures = artifacts["day25_figures"]
    recommended_titles = [row for row in titles if row.get("recommended") == "true"]
    title_lines = "\n".join(
        f"- [{row['candidate_id']}] {row['title_candidate']} ({row['paper_type']}; recommended={row['recommended']})"
        for row in titles
    )
    section_blocks = "\n\n".join(section_stub(row) for row in sections)
    forbidden = [row for row in claims if row.get("status") == "forbidden"]
    allowed = [row for row in claims if row.get("status") in {"allowed", "conditional", "diagnostic_only"}]
    forbidden_lines = "\n".join(f"- {row['claim_text']}: {row['forbidden_wording']}" for row in forbidden)
    allowed_lines = "\n".join(f"- {row['claim_text']}: {row['allowed_wording']}" for row in allowed)
    figure_lines = "\n".join(
        f"- {row['item_id']} ({row['item_type']}): {row['proposed_caption']} source={row['source_artifact']}"
        for row in figures
    )
    title = recommended_titles[0]["title_candidate"] if recommended_titles else "Diagnostic Benchmark Paper"
    return f"""# Diagnostic Benchmark Paper Skeleton

This paper is positioned as a diagnostic benchmark / failure-analysis contribution, not a validated Degen-LIO estimator method.

## Title Candidates

{title_lines}

Working title: **{title}**

## Abstract Skeleton

Background: LiDAR-inertial degeneracy can be diagnosed through controlled synthetic geometry and whitened information analysis.

Problem: Legacy toy evidence can be confounded by scene-family bias, and single metrics can fail strict validation.

Approach: We present a reproducible diagnostic benchmark, bias audit, unbiased toy probe, within-sequence/grouped/controlled metric stress tests, and a go/no-go claim-boundary gate.

Finding: The package supports diagnostic and failure-analysis claims, while method-update claims remain blocked.

Scope: No estimator update or weak-subspace update is implemented or authorized.

{section_blocks}

## Forbidden Claims

{forbidden_lines}

## Allowed Claims

{allowed_lines}

## Figure/Table Checklist

{figure_lines}
"""


def build_section_writing_tasks(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Turn Day 25 section outline into writing tasks."""

    rows = []
    for section in artifacts["day25_sections"]:
        rows.append(
            {
                "section_id": section["section_id"],
                "section_title": section["section_title"],
                "writing_task": f"Draft {section['section_title']} using the Day25 outline and keep the scope diagnostic.",
                "source_evidence": section["required_evidence"],
                "required_figures_tables": section["figures_tables"],
                "allowed_claims": section["claim_boundary"],
                "forbidden_claims": "no estimator-method validation; no weak-subspace update authorization; no robust ODI drift-prediction wording",
                "priority": "high" if section["section_title"] in {"Introduction", "Metric Validity Stress Tests", "Go/No-Go Gate and Claim Boundary"} else "medium",
                "owner_note": "write as paper skeleton prose, not implementation work",
            }
        )
    return rows


def build_figure_table_execution_plan(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Create figure/table execution rows without pretending pending items are generated."""

    rows = []
    for item in artifacts["day25_figures"]:
        is_existing_table = item["source_artifact"].endswith(".csv")
        rows.append(
            {
                "item_id": item["item_id"],
                "item_type": item["item_type"],
                "source_artifact": item["source_artifact"],
                "output_target": f"docs/paper/figures/{item['item_id']}.{'md' if item['item_type'] == 'table' else 'png'}",
                "generation_status": "source_available" if is_existing_table else "pending",
                "needed_script_or_manual_action": "convert CSV artifact into paper table" if is_existing_table else "write plotting script or create explicit placeholder plan; do not fake a rendered figure",
                "caption_draft": item["proposed_caption"],
                "must_show": item["must_show"],
                "must_not_claim": item["must_not_claim"],
                "priority": item["priority"],
            }
        )
    return rows


def build_readme_scope_update_plan(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        readme_row("Project scope", "State that this is a diagnostic benchmark / failure-analysis package.", "prevents method overclaiming", "This repository provides a reproducible diagnostic benchmark for LIO degeneracy analysis.", "Do not describe this repository as a validated Degen-LIO estimator method.", True),
        readme_row("Estimator method boundary", "State that Degen-LIO estimator update is not validated or implemented.", "matches Day22/24 gates", "No estimator update is authorized by the current evidence chain.", "Do not claim an estimator method contribution.", True),
        readme_row("Weak update boundary", "State that weak-subspace update remains unauthorized.", "prevents premature implementation claims", "Weak-subspace update remains gated and unauthorized.", "Do not provide instructions as if update logic exists.", True),
        readme_row("Reproduction commands", "List check_env, pytest, reproduce_day14, and Day15-Day26 scripts.", "artifact reviewers need exact commands", "Run the commands in order to rebuild diagnostics and tables.", "Do not imply hidden manual steps.", True),
        readme_row("Smoke vs real plot distinction", "Explain that Day14 reproduction uses smoke plotting/sensitivity for CI stability while real plot scripts remain available.", "avoids reproducibility confusion", "Smoke mode validates file/manifest structure; real rendering can be run separately.", "Do not state smoke figures are full real-rendered figures.", True),
        readme_row("Forbidden claims", "Include a claim-boundary list from Day25/26.", "writing guardrail", "Use claim-boundary tables before drafting abstracts or conclusions.", "Do not include robust ODI drift-prediction wording.", True),
        readme_row("Release package contents", "List configs, scripts, tests, reports, and selected tables/manifests.", "clarifies artifact scope", "Generated raw data may be rebuilt by scripts unless explicitly packaged.", "Do not package caches or repository internals.", True),
        readme_row("Known limitations", "List synthetic-only, toy_lio, failed validity screens, no method update, and small scene-family scope.", "reviewer risk transparency", "Limitations are part of the diagnostic contribution.", "Do not soften No-Go evidence.", True),
    ]


def build_release_cleanup_plan(_: Mapping[str, Any]) -> List[Dict[str, str]]:
    return [
        cleanup_row("CLEAN01", ".git", "present in repository checkout", "exclude from release archive unless sharing git history intentionally", True, "release package should not include repository internals"),
        cleanup_row("CLEAN02", ".pytest_cache", "ignored by .gitignore", "exclude from final archive", True, "cache files are not evidence"),
        cleanup_row("CLEAN03", "__pycache__", "ignored by .gitignore", "exclude from final archive", True, "compiled caches are not evidence"),
        cleanup_row("CLEAN04", "results/day14/raw/*.tum", "generated artifact", "decide whether to package or rebuild via reproduce_day14.sh", False, "raw trajectories can be regenerated"),
        cleanup_row("CLEAN05", "results/day30/tables/day15-day26*.csv", "key evidence tables", "force-add or document regeneration route for selected release", True, "paper evidence depends on CSV tables"),
        cleanup_row("CLEAN06", "final archive caches", "not cleaned by Day26", "exclude cache directories and font caches", True, "prevents noisy release bundles"),
        cleanup_row("CLEAN07", "README.md", "needs scope update", "add diagnostic benchmark scope and reproduction commands", True, "README is reviewer entry point"),
        cleanup_row("CLEAN08", "python3 -m pytest -q", "confirmed in current run when executed", "rerun before final package", True, "local quality gate"),
        cleanup_row("CLEAN09", "smoke vs real plots", "documented in plans, not yet README", "explain smoke reproduction versus real rendering", True, "prevents figure reproducibility confusion"),
    ]


def derive_day27_recommendation(artifacts: Mapping[str, Any]) -> List[Dict[str, str]]:
    method_allowed = bool(artifacts["day22_manifest"].get("method_update_authorized", False))
    return [
        {
            "recommended_day": "Day 27",
            "recommended_route": "README/release cleanup implementation",
            "task": "update README scope, reproduction commands, release exclusions, and forbidden claims",
            "allowed": str(not method_allowed).lower(),
            "reason": "Day26 release plan identifies README as blocking for release",
            "blocking_condition": "must not imply estimator method validation",
        },
        {
            "recommended_day": "Day 27",
            "recommended_route": "figure/table generation script planning",
            "task": "turn Day26 figure/table execution plan into safe scripts or table-generation placeholders",
            "allowed": str(not method_allowed).lower(),
            "reason": "figure/table execution plan contains pending items that must not be faked",
            "blocking_condition": "pending figures must remain marked pending until generated",
        },
        {
            "recommended_day": "Day 27",
            "recommended_route": "paper section draft expansion",
            "task": "expand skeleton sections into scoped draft prose",
            "allowed": str(not method_allowed).lower(),
            "reason": "paper skeleton is ready for prose expansion",
            "blocking_condition": "preserve claim-boundary language",
        },
        {
            "recommended_day": "Day 27",
            "recommended_route": "weak-subspace update implementation",
            "task": "implement estimator update",
            "allowed": "false",
            "reason": "blocked by Day22/25/26 evidence boundary",
            "blocking_condition": "requires future method_update_authorized=true",
        },
    ]


def write_day26_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    skeleton_path: Path,
    sections: Sequence[Mapping[str, str]],
    figures: Sequence[Mapping[str, str]],
    readme: Sequence[Mapping[str, str]],
    cleanup: Sequence[Mapping[str, str]],
    recommendation: Sequence[Mapping[str, str]],
    artifacts: Mapping[str, Any],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    method_update_authorized = bool(artifacts["day22_manifest"].get("method_update_authorized", False))
    weak_update_authorized = bool(artifacts["day22_manifest"].get("weak_update_authorized", False))
    route = next((row["recommended_route"] for row in recommendation if row["allowed"] == "true"), "none")
    manifest = {
        "status": "OK" if not missing and skeleton_path.exists() and skeleton_path.stat().st_size > 0 else "FAILED",
        "git_commit": git_commit(),
        "source_route": "diagnostic_benchmark_failure_analysis",
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "paper_skeleton_created": bool(skeleton_path.exists() and skeleton_path.stat().st_size > 0),
        "section_task_count": len(sections),
        "figure_table_task_count": len(figures),
        "readme_update_count": len(readme),
        "release_cleanup_count": len(cleanup),
        "recommended_day27_route": route,
        "method_update_authorized": method_update_authorized,
        "weak_update_authorized": weak_update_authorized,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "paper skeleton and release plan for diagnostic benchmark route; no estimator method update authorized",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def section_stub(row: Mapping[str, str]) -> str:
    return f"""## {row['section_title']}

Goal: {row['section_goal']}

Key points:
- {row['key_points']}

Evidence to cite:
- {row['required_evidence']}

Figures / tables:
- {row['figures_tables']}

Claim boundary:
- {row['claim_boundary']}

Writing risk:
- {row['writing_risk']}
"""


def write_markdown_table(path: Path, title: str, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "| " + " | ".join(fieldnames) + " |\n"
    sep = "| " + " | ".join("---" for _ in fieldnames) + " |\n"
    body = "".join("| " + " | ".join(str(row.get(field, "")).replace("\n", " ") for field in fieldnames) + " |\n" for row in rows)
    path.write_text(f"# {title}\n\n{header}{sep}{body}", encoding="utf-8")


def readme_row(section, update, reason, allowed, forbidden, blocking):
    return {
        "readme_section": section,
        "required_update": update,
        "reason": reason,
        "allowed_wording": allowed,
        "forbidden_wording": forbidden,
        "blocking": str(bool(blocking)).lower(),
    }


def cleanup_row(cid, pattern, status, action, blocking, reason):
    return {
        "cleanup_item": cid,
        "path_or_pattern": pattern,
        "current_status": status,
        "required_action": action,
        "blocking_for_release": str(bool(blocking)).lower(),
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
