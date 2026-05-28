import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/20_day27_release_cleanup.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day27"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day27_script_runs_release_audits_without_overwriting_inputs(tmp_path):
    repo_root = tmp_path / "repo"
    out_root = repo_root / "results/day30"
    reports_root = repo_root / "reports"
    prepare_day27_inputs(repo_root, out_root, reports_root)
    protected = snapshot_files(out_root)
    protected.update(snapshot_files(reports_root))
    config = write_day27_config(tmp_path)
    report = reports_root / "day27_release_cleanup_report.md"

    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
            "--repo-root",
            str(repo_root),
            "--out-root",
            str(out_root),
            "--reports-root",
            str(reports_root),
            "--readme",
            str(repo_root / "README.md"),
            "--report",
            str(report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    readme_audit = list(csv.DictReader((out_root / "tables/day27_readme_scope_audit.csv").open()))
    forbidden = list(csv.DictReader((out_root / "tables/day27_forbidden_claims_audit.csv").open()))
    path_audit = list(csv.DictReader((out_root / "tables/day27_release_forbidden_paths_audit.csv").open()))
    file_policy = list(csv.DictReader((out_root / "tables/day27_release_file_policy.csv").open()))
    archive = list(csv.DictReader((out_root / "tables/day27_safe_archive_plan.csv").open()))
    readiness = list(csv.DictReader((out_root / "tables/day27_figure_table_readiness.csv").open()))
    manifest = json.loads((out_root / "manifests/day27_release_cleanup_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert all(row["status"] == "pass" for row in readme_audit)
    assert all(row["status"] == "pass" for row in forbidden)
    audit_by_pattern = {row["path_pattern"]: row for row in path_audit}
    assert int(audit_by_pattern[".git"]["found_count"]) >= 1
    assert int(audit_by_pattern[".pytest_cache"]["found_count"]) >= 1
    assert int(audit_by_pattern["__pycache__"]["found_count"]) >= 1
    assert all(row["release_action"] == "exclude from release archive" for row in path_audit)
    assert any(row["path_or_pattern"] == "results/day30/tables/" for row in file_policy)
    assert any("git archive" in row["command_or_action"] for row in archive)
    assert readiness_status(readiness, "F01") == "pending"
    assert readiness_status(readiness, "F03") == "pending"
    assert any(row["readiness_status"] == "ready_for_conversion" for row in readiness)
    assert manifest["status"] == "OK"
    assert manifest["readme_scope_passed"] is True
    assert manifest["forbidden_claims_passed"] is True
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert "The repository remains a diagnostic benchmark / failure-analysis package, not a validated Degen-LIO estimator method." in report_text
    assert "Weak-subspace update remains unauthorized." in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day27_forbidden_claim_failure_is_clear(tmp_path):
    repo_root = tmp_path / "repo"
    out_root = repo_root / "results/day30"
    reports_root = repo_root / "reports"
    prepare_day27_inputs(repo_root, out_root, reports_root)
    readme = repo_root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nODI " + "robustly predicts drift.\n", encoding="utf-8")
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day27_config(tmp_path)),
            "--repo-root",
            str(repo_root),
            "--out-root",
            str(out_root),
            "--reports-root",
            str(reports_root),
            "--readme",
            str(readme),
            "--report",
            str(reports_root / "day27_release_cleanup_report.md"),
        ],
        tmp_path,
        check=False,
    )
    assert result.returncode == 1
    manifest = json.loads((out_root / "manifests/day27_release_cleanup_manifest.json").read_text())
    assert manifest["status"] == "FAILED"
    forbidden = list(csv.DictReader((out_root / "tables/day27_forbidden_claims_audit.csv").open()))
    assert any(row["status"] == "fail" for row in forbidden)


def prepare_day27_inputs(repo_root: Path, out_root: Path, reports_root: Path) -> None:
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    (repo_root / ".pytest_cache").mkdir(parents=True, exist_ok=True)
    (repo_root / "pkg/__pycache__").mkdir(parents=True, exist_ok=True)
    (out_root / "tables").mkdir(parents=True, exist_ok=True)
    (out_root / "manifests").mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)
    write_text(
        repo_root / "README.md",
        "diagnostic benchmark\nfailure-analysis\nnot a validated Degen-LIO estimator method\n"
        "Weak-subspace update remains unauthorized\nODI robust drift prediction is not validated\n",
    )
    for day, name in {
        24: "day24_diagnostic_consolidation_manifest.json",
        25: "day25_paper_outline_manifest.json",
        26: "day26_paper_skeleton_manifest.json",
    }.items():
        write_json(out_root / f"manifests/{name}", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
        report_name = {
            24: "day24_diagnostic_consolidation_report.md",
            25: "day25_paper_outline_report.md",
            26: "day26_paper_skeleton_report.md",
        }[day]
        write_text(reports_root / report_name, f"Day {day}\n")
    write_text(
        out_root / "tables/day26_figure_table_execution_plan.csv",
        "item_id,item_type,source_artifact,output_target,generation_status,needed_script_or_manual_action,caption_draft,must_show,must_not_claim,priority\n"
        "F01,figure,configs/minibench,docs/paper/figures/F01.png,pending,write script,geometry,scenes,real coverage,high\n"
        "F03,figure,day15/day16,docs/paper/figures/F03.png,pending,write script,bias,bias,toy real LIO,high\n"
        "T02,table,results/day30/tables/day18_sequence_validity_summary.csv,docs/paper/figures/T02.md,source_available,convert table,Day18,weak rho,robust prediction,high\n",
    )
    write_text(out_root / "tables/day26_readme_scope_update_plan.csv", "readme_section,required_update\nScope,diagnostic\n")
    write_text(out_root / "tables/day26_release_cleanup_plan.csv", "cleanup_item,path_or_pattern\nCLEAN01,.git\n")


def write_day27_config(tmp_path: Path) -> Path:
    path = tmp_path / "day27_release_cleanup.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day24_diagnostic_consolidation, day25_paper_outline, day26_paper_skeleton]",
                "route: README_release_cleanup",
                "forbidden_paths: [.git, .pytest_cache, __pycache__]",
                "required_readme_phrases:",
                "  - diagnostic benchmark",
                "  - failure-analysis",
                "  - not a validated Degen-LIO estimator method",
                "  - Weak-subspace update remains unauthorized",
                "  - ODI robust drift prediction is not validated",
                "forbidden_readme_phrases:",
                "  - ODI robustly predicts drift",
                "  - validated Degen-LIO estimator",
                "  - weak-subspace update is authorized",
                "  - ODI is superior to AIS/lambda_min",
                "  - Degen-LIO estimator method is validated",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def readiness_status(rows, item_id: str) -> str:
    return next(row for row in rows if row["item_id"] == item_id)["readiness_status"]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def snapshot_files(root: Path):
    return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}


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
