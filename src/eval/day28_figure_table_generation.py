"""Day 28 paper-ready table conversion and pending figure plans."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

GENERATED_INVENTORY_FIELDNAMES = [
    "item_id",
    "source_artifact",
    "output_markdown",
    "generated",
    "row_count",
    "paper_section",
    "claim_boundary",
    "must_not_claim",
]

PENDING_FIGURE_FIELDNAMES = [
    "item_id",
    "figure_name",
    "reason_pending",
    "required_source",
    "proposed_generation_script",
    "allowed_placeholder",
    "must_not_fake",
    "must_not_claim",
    "next_action",
]

CAPTION_FIELDNAMES = [
    "item_id",
    "caption_draft",
    "claim_boundary",
    "forbidden_wording",
    "source_artifact",
    "paper_section",
]

RECOMMENDATION_FIELDNAMES = [
    "recommended_day",
    "recommended_route",
    "task",
    "allowed",
    "reason",
    "blocking_condition",
]

TABLE_OUTPUTS = {
    "T01": "T01_day17_unbiased_probe_summary.md",
    "T02": "T02_day18_within_sequence_summary.md",
    "T03": "T03_day19_grouped_loso_summary.md",
    "T04": "T04_day20_controlled_partial_summary.md",
    "T05": "T05_day21_joint_risk_summary.md",
    "T06": "T06_day22_gate_decision.md",
    "T07": "T07_claim_boundary.md",
    "T08": "T08_reproducibility_commands.md",
}

PENDING_OUTPUTS = {
    "F01": "F01_benchmark_geometry_plan.md",
    "F03": "F03_bias_audit_figure_plan.md",
}

FORBIDDEN_CAPTION_WORDING = [
    "Do not claim robust ODI drift prediction.",
    "Do not claim a validated estimator method.",
    "Do not claim weak-subspace update authorization.",
    "Do not call toy_lio real LIO.",
    "Do not claim joint risk is a validated predictor.",
]


def load_day28_inputs(day30_root: Path, reports_root: Path) -> Dict[str, Any]:
    """Load Day 25-27 plans required for safe table conversion."""

    paths = {
        "day25_figure_plan": day30_root / "tables/day25_figure_table_plan.csv",
        "day25_claims": day30_root / "tables/day25_claim_boundary_for_paper.csv",
        "day25_manifest": day30_root / "manifests/day25_paper_outline_manifest.json",
        "day25_report": reports_root / "day25_paper_outline_report.md",
        "day26_figure_plan": day30_root / "tables/day26_figure_table_execution_plan.csv",
        "day26_manifest": day30_root / "manifests/day26_paper_skeleton_manifest.json",
        "day26_report": reports_root / "day26_paper_skeleton_report.md",
        "day27_readiness": day30_root / "tables/day27_figure_table_readiness.csv",
        "day27_manifest": day30_root / "manifests/day27_release_cleanup_manifest.json",
        "day27_report": reports_root / "day27_release_cleanup_report.md",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day28 input file(s): "
            + "; ".join(missing)
            + ". Run Day 25-27 scripts before Day 28 figure/table generation."
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


def load_figure_table_readiness(artifacts: Mapping[str, Any]) -> Dict[str, Dict[str, str]]:
    return {row["item_id"]: dict(row) for row in artifacts["day27_readiness"]}


def convert_csv_to_markdown_table(source_path: Path, output_path: Path, title: str, caption: str, claim_boundary: str) -> int:
    rows = read_csv_rows(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        with source_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            fieldnames = next(reader, [])
    header = "| " + " | ".join(escape_cell(field) for field in fieldnames) + " |"
    sep = "| " + " | ".join("---" for _ in fieldnames) + " |"
    body = [
        "| " + " | ".join(escape_cell(row.get(field, "")) for field in fieldnames) + " |"
        for row in rows
    ]
    output_path.write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                caption,
                "",
                f"Claim boundary: {claim_boundary}",
                "",
                header,
                sep,
                *body,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return len(rows)


def build_generated_table_inventory(
    *,
    readiness: Mapping[str, Mapping[str, str]],
    day25_plan: Sequence[Mapping[str, str]],
    generated_dir: Path,
    table_items: Sequence[str],
) -> tuple[List[Dict[str, str]], List[Path]]:
    """Convert ready table CSVs into Markdown and return inventory rows."""

    plan_by_id = {row["item_id"]: dict(row) for row in day25_plan}
    inventory: List[Dict[str, str]] = []
    outputs: List[Path] = []
    for item_id in table_items:
        item = dict(readiness.get(item_id, {}))
        plan = dict(plan_by_id.get(item_id, {}))
        if item.get("readiness_status") != "ready_for_conversion":
            inventory.append(inventory_row(item_id, item.get("source_artifact", ""), "", False, 0, plan.get("paper_section", ""), "not ready for conversion", item.get("must_not_claim", "")))
            continue
        source_path = ROOT / item["source_artifact"]
        output_path = generated_dir / TABLE_OUTPUTS[item_id]
        claim_boundary = safe_claim_boundary(item_id, item, plan)
        caption = safe_caption(item_id, plan.get("proposed_caption", item_id), claim_boundary)
        if not source_path.exists():
            inventory.append(inventory_row(item_id, item["source_artifact"], relative_to_root(output_path), False, 0, plan.get("paper_section", ""), f"missing source: {relative_to_root(source_path)}", item.get("must_not_claim", "")))
            continue
        row_count = convert_csv_to_markdown_table(source_path, output_path, item_id, caption, claim_boundary)
        outputs.append(output_path)
        inventory.append(inventory_row(item_id, item["source_artifact"], relative_to_root(output_path), True, row_count, plan.get("paper_section", ""), claim_boundary, item.get("must_not_claim", "")))
    return inventory, outputs


def build_pending_figure_plan(
    *,
    readiness: Mapping[str, Mapping[str, str]],
    day25_plan: Sequence[Mapping[str, str]],
    pending_dir: Path,
    pending_items: Sequence[str],
) -> tuple[List[Dict[str, str]], List[Path]]:
    """Write explicit pending plans for figures without creating fake images."""

    plan_by_id = {row["item_id"]: dict(row) for row in day25_plan}
    rows: List[Dict[str, str]] = []
    outputs: List[Path] = []
    for item_id in pending_items:
        item = dict(readiness.get(item_id, {}))
        plan = dict(plan_by_id.get(item_id, {}))
        figure_name = {
            "F01": "benchmark geometry overview",
            "F03": "legacy vs unbiased toy_lio bias audit",
        }.get(item_id, item_id)
        row = {
            "item_id": item_id,
            "figure_name": figure_name,
            "reason_pending": "requires a real generation script; no rendered figure is produced on Day 28",
            "required_source": item.get("source_artifact", plan.get("source_artifact", "")),
            "proposed_generation_script": f"scripts/paper_figures/generate_{item_id.lower()}.py",
            "allowed_placeholder": "true",
            "must_not_fake": "true",
            "must_not_claim": item.get("must_not_claim", plan.get("must_not_claim", "")),
            "next_action": "implement a real figure-generation script or keep this markdown plan as placeholder",
        }
        rows.append(row)
        output_path = pending_dir / PENDING_OUTPUTS[item_id]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_pending_figure_plan(row), encoding="utf-8")
        outputs.append(output_path)
    return rows, outputs


def build_caption_bank(
    *,
    day25_plan: Sequence[Mapping[str, str]],
    generated_inventory: Sequence[Mapping[str, str]],
    pending_figures: Sequence[Mapping[str, str]],
    caption_path: Path,
) -> tuple[List[Dict[str, str]], Path]:
    plan_by_id = {row["item_id"]: dict(row) for row in day25_plan}
    caption_rows: List[Dict[str, str]] = []
    item_ids = [row["item_id"] for row in generated_inventory] + [row["item_id"] for row in pending_figures]
    for item_id in item_ids:
        plan = plan_by_id.get(item_id, {})
        boundary = safe_claim_boundary(item_id, {}, plan)
        caption_rows.append(
            {
                "item_id": item_id,
                "caption_draft": safe_caption(item_id, plan.get("proposed_caption", item_id), boundary),
                "claim_boundary": boundary,
                "forbidden_wording": " ".join(FORBIDDEN_CAPTION_WORDING),
                "source_artifact": plan.get("source_artifact", ""),
                "paper_section": plan.get("paper_section", ""),
            }
        )
    caption_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Caption Bank", ""]
    for row in caption_rows:
        lines.extend(
            [
                f"## {row['item_id']}",
                "",
                row["caption_draft"],
                "",
                f"Claim boundary: {row['claim_boundary']}",
                "",
                f"Forbidden wording: {row['forbidden_wording']}",
                "",
            ]
        )
    caption_path.write_text("\n".join(lines), encoding="utf-8")
    return caption_rows, caption_path


def build_day29_recommendation() -> List[Dict[str, str]]:
    return [
        {
            "recommended_day": "Day 29",
            "recommended_route": "paper section drafting",
            "task": "insert generated tables into section drafts and expand text using claim boundaries",
            "allowed": "true",
            "reason": "Day28 produces paper-ready tables and caption bank",
            "blocking_condition": "do not convert pending figure plans into fake figures",
        },
        {
            "recommended_day": "Day 29",
            "recommended_route": "safe figure-generation script implementation",
            "task": "implement real scripts for F01/F03 or keep them pending with explicit plan",
            "allowed": "true",
            "reason": "F01 and F03 remain pending and require real generation scripts",
            "blocking_condition": "must not generate fake PNG/PDF",
        },
        {
            "recommended_day": "Day 29",
            "recommended_route": "weak-subspace update implementation",
            "task": "implement estimator update",
            "allowed": "false",
            "reason": "method update remains unauthorized",
            "blocking_condition": "requires future method_update_authorized=true",
        },
    ]


def write_day28_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    generated_inventory: Sequence[Mapping[str, str]],
    pending_figures: Sequence[Mapping[str, str]],
    captions: Sequence[Mapping[str, str]],
    artifacts: Mapping[str, Any],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    generated_count = sum(row.get("generated") == "true" for row in generated_inventory)
    fake_figures_created = any((ROOT / f"docs/paper/pending_figures/{row['item_id']}.png").exists() for row in pending_figures)
    method_update_authorized = bool(artifacts["day27_manifest"].get("method_update_authorized", False))
    weak_update_authorized = bool(artifacts["day27_manifest"].get("weak_update_authorized", False))
    manifest = {
        "status": "OK" if not missing and generated_count >= 8 and len(pending_figures) >= 2 and not fake_figures_created else "FAILED",
        "git_commit": git_commit(),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "generated_table_count": int(generated_count),
        "pending_figure_count": len(pending_figures),
        "caption_count": len(captions),
        "fake_figures_created": bool(fake_figures_created),
        "method_update_authorized": method_update_authorized,
        "weak_update_authorized": weak_update_authorized,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "paper-ready table conversion and pending figure plans only; no fake plots and no method update",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def inventory_row(item_id, source, output, generated, row_count, section, boundary, must_not_claim):
    return {
        "item_id": item_id,
        "source_artifact": source,
        "output_markdown": output,
        "generated": str(bool(generated)).lower(),
        "row_count": str(row_count),
        "paper_section": section,
        "claim_boundary": boundary,
        "must_not_claim": must_not_claim,
    }


def safe_claim_boundary(item_id: str, readiness: Mapping[str, str], plan: Mapping[str, str]) -> str:
    must_not = readiness.get("must_not_claim") or plan.get("must_not_claim") or "overclaiming"
    return f"Diagnostic benchmark evidence only; do not claim {must_not}."


def safe_caption(item_id: str, caption: str, boundary: str) -> str:
    text = caption.strip().rstrip(".")
    return f"{text}. This item supports diagnostic benchmark interpretation only; {boundary}"


def render_pending_figure_plan(row: Mapping[str, str]) -> str:
    return f"""# Pending Figure Plan: {row['item_id']} {row['figure_name']}

Reason pending: {row['reason_pending']}

Required source: {row['required_source']}

Proposed generation script: `{row['proposed_generation_script']}`

Allowed placeholder: {row['allowed_placeholder']}

Must not fake: {row['must_not_fake']}

Must not claim: {row['must_not_claim']}

Next action: {row['next_action']}
"""


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def escape_cell(value: object) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text


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
