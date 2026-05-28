"""Day 29 safe figure generation and table interpretation safeguards."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

FIGURE_INVENTORY_FIELDNAMES = [
    "figure_id",
    "source_artifacts",
    "output_png",
    "output_pdf",
    "png_exists",
    "pdf_exists",
    "png_size_bytes",
    "pdf_size_bytes",
    "real_generation_status",
    "fake_figure_detected",
    "claim_boundary",
    "must_not_claim",
]

TABLE_SAFETY_FIELDNAMES = [
    "table_id",
    "table_path",
    "risk_type",
    "unsafe_or_ambiguous_text",
    "required_note",
    "fixed_or_noted",
    "reason",
]

CAPTION_AUDIT_FIELDNAMES = [
    "item_id",
    "caption_or_note_path",
    "forbidden_phrase",
    "found",
    "status",
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

FORBIDDEN_PHRASES = [
    "ODI robustly predicts drift",
    "validated Degen-LIO estimator",
    "weak-subspace update is authorized",
    "toy_lio is real LIO",
    "joint risk predicts drift",
    "ODI is superior to AIS/lambda_min",
]

FIGURE_SPECS = {
    "F01": {
        "source_artifacts": "configs/minibench/*.yaml; data/minibench/*/feature_points.csv; data/minibench/*/axis.csv; data/minibench/*/planes.csv; data/minibench/*/scene_metadata.json",
        "output_png": "docs/paper/figures/F01_benchmark_geometry_overview.png",
        "output_pdf": "docs/paper/figures/F01_benchmark_geometry_overview.pdf",
        "claim_boundary": "Diagnostic geometry overview only; no real-world estimator validation claim.",
        "must_not_claim": "real-world coverage",
    },
    "F03": {
        "source_artifacts": "results/day30/tables/day15_bias_audit.csv; results/day30/tables/day16_unbiased_toy_lio_summary.csv",
        "output_png": "docs/paper/figures/F03_bias_audit_legacy_vs_unbiased.png",
        "output_pdf": "docs/paper/figures/F03_bias_audit_legacy_vs_unbiased.pdf",
        "claim_boundary": "Bias audit of synthetic toy_lio protocol only; toy_lio is not real LIO.",
        "must_not_claim": "real LIO validation",
    },
}


def load_day29_inputs(day30_root: Path, reports_root: Path) -> Dict[str, Any]:
    paths = {
        "day15_bias_audit": day30_root / "tables/day15_bias_audit.csv",
        "day16_summary": day30_root / "tables/day16_unbiased_toy_lio_summary.csv",
        "day27_readiness": day30_root / "tables/day27_figure_table_readiness.csv",
        "day27_manifest": day30_root / "manifests/day27_release_cleanup_manifest.json",
        "day27_report": reports_root / "day27_release_cleanup_report.md",
        "day28_inventory": day30_root / "tables/day28_generated_table_inventory.csv",
        "day28_pending": day30_root / "tables/day28_pending_figure_plan.csv",
        "day28_caption": day30_root / "tables/day28_caption_bank.csv",
        "day28_manifest": day30_root / "manifests/day28_figure_table_generation_manifest.json",
        "day28_report": reports_root / "day28_figure_table_generation_report.md",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day29 input file(s): "
            + "; ".join(missing)
            + ". Run Day 15/16/27/28 scripts before Day 29 safe figures."
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


def run_safe_figure_generation(data_root: Path, config_root: Path, day30_root: Path, docs_root: Path) -> None:
    out_dir = docs_root / "figures"
    command = [
        sys.executable,
        str(ROOT / "scripts/paper_figures/generate_day29_figures.py"),
        "--data-root",
        str(data_root),
        "--config-root",
        str(config_root),
        "--day30-root",
        str(day30_root),
        "--out-dir",
        str(out_dir),
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Day29 figure generation failed.\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )


def audit_generated_figures(docs_root: Path, min_size_bytes: int = 2000) -> List[Dict[str, str]]:
    rows = []
    for figure_id, spec in FIGURE_SPECS.items():
        png = ROOT / spec["output_png"] if not docs_root else docs_root / "figures" / Path(spec["output_png"]).name
        pdf = ROOT / spec["output_pdf"] if not docs_root else docs_root / "figures" / Path(spec["output_pdf"]).name
        png_size = png.stat().st_size if png.exists() else 0
        pdf_size = pdf.stat().st_size if pdf.exists() else 0
        fake = (not png.exists()) or (not pdf.exists()) or png_size < min_size_bytes or pdf_size < min_size_bytes
        rows.append(
            {
                "figure_id": figure_id,
                "source_artifacts": spec["source_artifacts"],
                "output_png": relative_to_root(png),
                "output_pdf": relative_to_root(pdf),
                "png_exists": str(png.exists()).lower(),
                "pdf_exists": str(pdf.exists()).lower(),
                "png_size_bytes": str(png_size),
                "pdf_size_bytes": str(pdf_size),
                "real_generation_status": "generated_from_source_artifacts" if not fake else "failed_or_placeholder_sized",
                "fake_figure_detected": str(bool(fake)).lower(),
                "claim_boundary": spec["claim_boundary"],
                "must_not_claim": spec["must_not_claim"],
            }
        )
    return rows


def build_table_safety_notes(output_path: Path) -> List[Dict[str, str]]:
    rows = [
        safety_row("T03", "docs/paper/generated_tables/T03_day19_grouped_loso_summary.md", "ambiguous validity wording", "held_out_validity_status = valid", "valid means computable, not substantive validity; held-out rows still require effect-size and claim-boundary interpretation", True, "prevents LOSO computability from being read as scientific success"),
        safety_row("T03", "docs/paper/generated_tables/T03_day19_grouped_loso_summary.md", "ambiguous validity wording", "remains valid", "valid means computable, not substantive validity; do not present LOSO status as robust generalization", True, "preserves Day19 negative evidence"),
        safety_row("T05", "docs/paper/generated_tables/T05_day21_joint_risk_summary.md", "baseline comparison ambiguity", "beats_no_odi_baseline for no-ODI baseline", "no-ODI baseline cannot beat itself; interpret this field only for with-ODI joint features", True, "prevents circular baseline interpretation"),
        safety_row("T05", "docs/paper/generated_tables/T05_day21_joint_risk_summary.md", "status overread risk", "exploratory_not_validated rows", "exploratory_not_validated means the feature did not pass the strict Day21 gate", True, "prevents exploratory rows from being cited as validated predictors"),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Table Interpretation Notes",
        "",
        "These notes are part of the paper safety layer. They preserve negative evidence and prevent computable statuses from being read as substantive scientific validity.",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['table_id']} - {row['risk_type']}",
                "",
                f"Ambiguous text: `{row['unsafe_or_ambiguous_text']}`",
                "",
                f"Required note: {row['required_note']}",
                "",
                f"Reason: {row['reason']}",
                "",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return rows


def build_caption_safety_audit(paths: Sequence[Path]) -> List[Dict[str, str]]:
    rows = []
    for path in paths:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        item_id = path.stem
        for phrase in FORBIDDEN_PHRASES:
            found = phrase in text
            rows.append(
                {
                    "item_id": item_id,
                    "caption_or_note_path": relative_to_root(path),
                    "forbidden_phrase": phrase,
                    "found": str(found).lower(),
                    "status": "fail" if found else "pass",
                    "reason": "forbidden wording present" if found else "forbidden wording absent",
                }
            )
    return rows


def build_day30_recommendation() -> List[Dict[str, str]]:
    return [
        {
            "recommended_day": "Day 30",
            "recommended_route": "final package review",
            "task": "audit final artifacts, manifests, figures, generated tables, release docs, and claim boundaries",
            "allowed": "true",
            "reason": "Day29 creates real F01/F03 figures and paper-ready tables",
            "blocking_condition": "must preserve No-Go method boundary",
        },
        {
            "recommended_day": "Day 30",
            "recommended_route": "release readiness check",
            "task": "run full pytest, verify manifests, inspect archive plan, and prepare release checklist",
            "allowed": "true",
            "reason": "release hygiene is now documented and audited",
            "blocking_condition": "must not package cache or fake figures",
        },
        {
            "recommended_day": "Day 30",
            "recommended_route": "weak-subspace update implementation",
            "task": "implement estimator update",
            "allowed": "false",
            "reason": "method update remains unauthorized",
            "blocking_condition": "requires future method_update_authorized=true",
        },
    ]


def write_day29_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    figure_inventory: Sequence[Mapping[str, str]],
    safety_notes: Sequence[Mapping[str, str]],
    caption_audit: Sequence[Mapping[str, str]],
    artifacts: Mapping[str, Any],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    generated_figure_count = sum(row["real_generation_status"] == "generated_from_source_artifacts" for row in figure_inventory)
    fake_figures_created = any(row["fake_figure_detected"] == "true" for row in figure_inventory)
    caption_safety_passed = all(row["status"] == "pass" for row in caption_audit)
    method_update_authorized = bool(artifacts["day28_manifest"].get("method_update_authorized", False))
    weak_update_authorized = bool(artifacts["day28_manifest"].get("weak_update_authorized", False))
    manifest = {
        "status": "OK" if not missing and generated_figure_count >= 2 and not fake_figures_created and safety_notes and caption_safety_passed else "FAILED",
        "git_commit": git_commit(),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "generated_figure_count": int(generated_figure_count),
        "fake_figures_created": bool(fake_figures_created),
        "table_safety_notes_created": bool(safety_notes),
        "caption_safety_passed": bool(caption_safety_passed),
        "method_update_authorized": method_update_authorized,
        "weak_update_authorized": weak_update_authorized,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "real F01/F03 figures plus table interpretation safeguards; no method update authorized",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def safety_row(table_id, table_path, risk_type, text, note, fixed, reason):
    return {
        "table_id": table_id,
        "table_path": table_path,
        "risk_type": risk_type,
        "unsafe_or_ambiguous_text": text,
        "required_note": note,
        "fixed_or_noted": str(bool(fixed)).lower(),
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
