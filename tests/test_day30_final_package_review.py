import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.day30_final_package_review import audit_global_claim_boundaries, required_artifacts, resolve_artifact_path


SCRIPT = ROOT / "scripts/23_day30_final_package_review.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day30"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day30_script_runs_final_package_review_without_overwriting_inputs(tmp_path):
    repo_root = tmp_path / "repo"
    day14_root = repo_root / "results/day14"
    out_root = repo_root / "results/day30"
    reports_root = repo_root / "reports"
    docs_root = repo_root / "docs"
    prepare_day30_inputs(repo_root, day14_root, out_root, reports_root, docs_root)
    protected = snapshot_existing_inputs(repo_root, day14_root, out_root, reports_root)
    config = write_day30_config(tmp_path)
    report = reports_root / "day30_final_package_review.md"
    release_notes = docs_root / "release/day30_final_release_notes.md"

    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
            "--repo-root",
            str(repo_root),
            "--day14-root",
            str(day14_root),
            "--out-root",
            str(out_root),
            "--reports-root",
            str(reports_root),
            "--docs-root",
            str(docs_root),
            "--report",
            str(report),
            "--release-notes",
            str(release_notes),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    required = list(csv.DictReader((out_root / "tables/day30_required_artifact_audit.csv").open()))
    figure_audit = list(csv.DictReader((out_root / "tables/day30_figure_table_final_audit.csv").open()))
    claim_audit = list(csv.DictReader((out_root / "tables/day30_global_claim_boundary_audit.csv").open()))
    checklist = list(csv.DictReader((out_root / "tables/day30_release_readiness_checklist.csv").open()))
    decision = list(csv.DictReader((out_root / "tables/day30_final_decision.csv").open()))
    manifest = json.loads((out_root / "manifests/day30_final_package_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert {row["day"] for row in required} >= {f"Day {day}" for day in range(15, 30)}
    assert all(row["status"] == "pass" for row in required)
    f01_rows = [row for row in figure_audit if row["item_id"] == "F01"]
    f03_rows = [row for row in figure_audit if row["item_id"] == "F03"]
    assert f01_rows and f03_rows
    assert all(row["real_or_placeholder"] == "real" for row in f01_rows + f03_rows)
    assert all(row["status"] == "pass" for row in figure_audit)
    assert any(row["context_type"] in {"boundary_text", "negated_or_unvalidated_text"} for row in claim_audit)
    assert all(row["status"] != "fail" for row in claim_audit)
    assert checklist_status(checklist, "full pytest confirmed locally") == "manual_required"
    assert decision_authorized(decision, "method update authorized") == "false"
    assert decision_authorized(decision, "weak-subspace update authorized") == "false"
    assert decision_authorized(decision, "ODI robust drift claim allowed") == "false"
    assert manifest["status"] in {"OK", "CONDITIONAL_OK"}
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert manifest["odi_robust_claim_allowed"] is False
    assert manifest["fake_figures_detected"] is False
    assert "The project is not a validated Degen-LIO estimator method." in report_text
    assert "Weak-subspace update remains unauthorized." in report_text
    assert "ODI robust drift prediction remains unvalidated." in report_text
    assert "ODI " + "robustly predicts drift" not in report_text
    assert release_notes.exists() and release_notes.stat().st_size > 0


def test_day30_claim_audit_separates_negated_and_positive_forbidden_claims(tmp_path):
    repo_root = tmp_path / "repo"
    write_text(
        repo_root / "README.md",
        "This is not a validated Degen-LIO estimator method.\n"
        "Weak-subspace update remains unauthorized.\n",
    )
    write_text(repo_root / "docs/paper/claim_boundary.md", "Forbidden Claims: ODI " + "robustly predicts drift\n")
    write_text(repo_root / "reports/bad.md", "ODI " + "robustly predicts drift in this benchmark.\n")

    rows = audit_global_claim_boundaries(repo_root)
    assert any(row["status"] == "pass_with_context" and "not a validated" in row["matched_text"] for row in rows)
    assert any(row["status"] == "pass_with_context" and "Forbidden Claims" in row["matched_text"] for row in rows)
    assert any(row["status"] == "fail" and "reports/bad.md" in row["file_path"] for row in rows)


def prepare_day30_inputs(repo_root: Path, day14_root: Path, out_root: Path, reports_root: Path, docs_root: Path) -> None:
    for root in [day14_root / "manifests", day14_root / "tables", out_root / "tables", out_root / "manifests", reports_root, docs_root]:
        root.mkdir(parents=True, exist_ok=True)
    write_text(
        repo_root / "README.md",
        "diagnostic benchmark\nfailure-analysis\nnot a validated Degen-LIO estimator method\n"
        "Weak-subspace update remains unauthorized\nODI robust drift prediction is not validated\n"
        "python3 scripts/check_env.py\npython3 -m pytest -q\nsmoke plotting and real plotting are documented\n",
    )
    for artifact in required_artifacts():
        path = resolve_artifact_path(artifact.path, repo_root, day14_root, out_root, reports_root)
        if path.suffix == ".json":
            payload = {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False}
            if "day29_safe_figures_manifest" in path.name:
                payload.update({"fake_figures_created": False})
            write_json(path, payload)
        elif path.suffix == ".csv":
            write_text(path, "col_a,col_b\nvalue,diagnostic boundary\n")
        elif path.suffix in {".png", ".pdf"}:
            write_bytes(path, b"real-figure-bytes" * 300)
        else:
            write_text(path, "diagnostic benchmark / failure-analysis boundary\n")
    for name in [
        "T01_day17_unbiased_probe_summary.md",
        "T02_day18_within_sequence_summary.md",
        "T03_day19_grouped_loso_summary.md",
        "T04_day20_controlled_partial_summary.md",
        "T05_day21_joint_risk_summary.md",
        "T06_day22_gate_decision.md",
        "T07_claim_boundary.md",
        "T08_reproducibility_commands.md",
    ]:
        write_text(docs_root / "paper/generated_tables" / name, "diagnostic table\n")
    write_text(
        docs_root / "paper/generated_tables/table_interpretation_notes.md",
        "valid means computable, not substantive validity\n",
    )
    write_text(docs_root / "paper/caption_bank.md", "Claim boundary captions only\n")
    write_text(docs_root / "paper/caption_bank_day29.md", "Day29 caption boundary only\n")
    write_bytes(docs_root / "paper/figures/F01_benchmark_geometry_overview.png", b"real-f01-png" * 300)
    write_bytes(docs_root / "paper/figures/F01_benchmark_geometry_overview.pdf", b"real-f01-pdf" * 300)
    write_bytes(docs_root / "paper/figures/F03_bias_audit_legacy_vs_unbiased.png", b"real-f03-png" * 300)
    write_bytes(docs_root / "paper/figures/F03_bias_audit_legacy_vs_unbiased.pdf", b"real-f03-pdf" * 300)
    write_text(docs_root / "paper/diagnostic_benchmark_paper_skeleton.md", "diagnostic benchmark / failure-analysis\n")
    write_text(docs_root / "release/release_scope.md", "diagnostic benchmark release scope\n")
    write_text(docs_root / "release/release_cleanup_policy.md", "exclude .git .pytest_cache __pycache__\n")
    write_text(docs_root / "release/release_reproducibility_commands.md", "python3 -m pytest -q\n")
    write_text(
        out_root / "tables/day29_generated_figure_inventory.csv",
        "figure_id,source_artifacts,output_png,output_pdf,png_exists,pdf_exists,png_size_bytes,pdf_size_bytes,real_generation_status,fake_figure_detected,claim_boundary,must_not_claim\n"
        "F01,source,docs/paper/figures/F01_benchmark_geometry_overview.png,docs/paper/figures/F01_benchmark_geometry_overview.pdf,true,true,3000,3000,generated_from_source_artifacts,false,boundary,none\n"
        "F03,source,docs/paper/figures/F03_bias_audit_legacy_vs_unbiased.png,docs/paper/figures/F03_bias_audit_legacy_vs_unbiased.pdf,true,true,3000,3000,generated_from_source_artifacts,false,boundary,none\n",
    )


def write_day30_config(tmp_path: Path) -> Path:
    path = tmp_path / "day30_final_package_review.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day14_reproduction, day15_bias_audit, day29_safe_figures]",
                "route: final_package_review",
                "final_review_goals: [artifact_completeness_audit, figure_table_final_audit, claim_boundary_global_audit, release_readiness_check, clean_archive_plan, final_decision_report]",
                "forbidden_actions: [weak_subspace_update, estimator_method_implementation, robust_ODI_claim, validated_Degen_LIO_method_claim, fake_figure_generation, overwrite_previous_artifacts]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def checklist_status(rows, item: str) -> str:
    return next(row for row in rows if row["check_item"] == item)["status"]


def decision_authorized(rows, item: str) -> str:
    return next(row for row in rows if row["decision_item"] == item)["authorized"]


def snapshot_existing_inputs(repo_root: Path, day14_root: Path, out_root: Path, reports_root: Path):
    protected = {}
    for artifact in required_artifacts():
        path = resolve_artifact_path(artifact.path, repo_root, day14_root, out_root, reports_root)
        if path.exists():
            protected[path] = path.read_bytes()
    return protected


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_script(command, tmp_path: Path, check: bool = True):
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=child_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
    if check:
        result.check_returncode()
    return result
