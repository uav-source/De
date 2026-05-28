import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/21_day28_figure_table_generation.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day28"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day28_script_generates_tables_and_pending_plans_without_fake_figures(tmp_path):
    repo_root = tmp_path / "repo"
    out_root = repo_root / "results/day30"
    reports_root = repo_root / "reports"
    docs_root = repo_root / "docs/paper"
    prepare_day28_inputs(repo_root, out_root, reports_root)
    protected = snapshot_files(out_root)
    protected.update(snapshot_files(reports_root))
    config = write_day28_config(tmp_path)
    report = reports_root / "day28_figure_table_generation_report.md"

    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
            "--out-root",
            str(out_root),
            "--reports-root",
            str(reports_root),
            "--docs-root",
            str(docs_root),
            "--report",
            str(report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    expected_tables = [
        "T01_day17_unbiased_probe_summary.md",
        "T02_day18_within_sequence_summary.md",
        "T03_day19_grouped_loso_summary.md",
        "T04_day20_controlled_partial_summary.md",
        "T05_day21_joint_risk_summary.md",
        "T06_day22_gate_decision.md",
        "T07_claim_boundary.md",
        "T08_reproducibility_commands.md",
    ]
    for name in expected_tables:
        path = docs_root / "generated_tables" / name
        assert path.exists()
        assert path.stat().st_size > 0
    assert (docs_root / "pending_figures/F01_benchmark_geometry_plan.md").exists()
    assert (docs_root / "pending_figures/F03_bias_audit_figure_plan.md").exists()
    assert not (docs_root / "pending_figures/F01.png").exists()
    assert not (docs_root / "pending_figures/F03.png").exists()
    assert not list((docs_root / "pending_figures").glob("*.pdf"))
    captions = (docs_root / "caption_bank.md").read_text(encoding="utf-8")
    for phrase in [
        "ODI " + "robustly predicts drift",
        "validated Degen-LIO estimator",
        "weak-subspace update is authorized",
        "toy_lio is real LIO",
        "joint risk predicts drift",
    ]:
        assert phrase not in captions

    inventory = list(csv.DictReader((out_root / "tables/day28_generated_table_inventory.csv").open()))
    pending = list(csv.DictReader((out_root / "tables/day28_pending_figure_plan.csv").open()))
    manifest = json.loads((out_root / "manifests/day28_figure_table_generation_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")
    assert len([row for row in inventory if row["generated"] == "true"]) >= 8
    assert {row["item_id"] for row in pending} == {"F01", "F03"}
    assert all(row["must_not_fake"] == "true" for row in pending)
    assert manifest["status"] == "OK"
    assert manifest["generated_table_count"] >= 8
    assert manifest["pending_figure_count"] >= 2
    assert manifest["fake_figures_created"] is False
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert "No fake figures are generated." in report_text
    assert "Weak-subspace update remains unauthorized." in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day28_missing_inputs_are_clear(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day28_config(tmp_path)),
            "--out-root",
            str(tmp_path / "missing/results/day30"),
            "--reports-root",
            str(tmp_path / "missing/reports"),
            "--docs-root",
            str(tmp_path / "docs/paper"),
            "--report",
            str(tmp_path / "reports/day28_figure_table_generation_report.md"),
        ],
        tmp_path,
        check=False,
    )
    assert result.returncode == 2
    assert "Missing required Day28 input file" in result.stderr


def prepare_day28_inputs(repo_root: Path, out_root: Path, reports_root: Path) -> None:
    (out_root / "tables").mkdir(parents=True, exist_ok=True)
    (out_root / "manifests").mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)
    for name in [
        "day25_paper_outline_manifest.json",
        "day26_paper_skeleton_manifest.json",
        "day27_release_cleanup_manifest.json",
    ]:
        write_json(out_root / f"manifests/{name}", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
    for report in [
        "day25_paper_outline_report.md",
        "day26_paper_skeleton_report.md",
        "day27_release_cleanup_report.md",
    ]:
        write_text(reports_root / report, "ok\n")
    write_text(
        out_root / "tables/day25_figure_table_plan.csv",
        "item_id,item_type,proposed_caption,source_artifact,purpose,must_show,must_not_claim,paper_section,priority\n"
        "F01,figure,Benchmark geometry overview,configs/minibench,overview,scenes,real coverage,Benchmark,high\n"
        "F03,figure,Legacy vs unbiased toy_lio bias audit,results/day30/tables/day15_bias_audit.csv,show bias,bias,real LIO validation,Bias Audit,high\n"
        "T01,table,Day17 unbiased trial summary,results/day30/tables/day17_unbiased_probe_summary.csv,summary,n_trials,metric validation,Bias Audit,medium\n"
        "T02,table,Day18 within-sequence validation,results/day30/tables/day18_sequence_validity_summary.csv,stress,weak rho,robust prediction,Metric Validity,high\n"
        "T03,table,Day19 grouped LOSO summary,results/day30/tables/day19_loso_selection_results.csv,heldout,loso,generalized validity,Metric Validity,high\n"
        "T04,table,Day20 controlled partial validity,results/day30/tables/day20_incremental_validity_summary.csv,controlled,small rho,substantive validity if failed,Metric Validity,high\n"
        "T05,table,Day21 joint risk comparison,results/day30/tables/day21_joint_risk_comparison.csv,joint,comparison,validated joint-risk detector,Metric Validity,medium\n"
        "T06,table,Day22 gate decision,results/day30/tables/day22_gate_decision.csv,gate,no go,Go method result,Gate,high\n"
        "T07,table,Claim boundary table,results/day30/tables/day25_claim_boundary_for_paper.csv,boundary,claims,forbidden claims as conclusions,Gate,high\n"
        "T08,table,Reproducibility command table,results/day30/tables/day25_reproducibility_plan.csv,repro,commands,full real-render guarantee from smoke path,Repro,high\n",
    )
    write_text(
        out_root / "tables/day26_figure_table_execution_plan.csv",
        "item_id,item_type,source_artifact,output_target,generation_status,needed_script_or_manual_action,caption_draft,must_show,must_not_claim,priority\n"
        "F01,figure,configs/minibench,docs/paper/figures/F01.png,pending,write script,geometry,scenes,real coverage,high\n"
        "F03,figure,results/day30/tables/day15_bias_audit.csv,docs/paper/figures/F03.png,pending,write script,bias,bias,real LIO validation,high\n",
    )
    write_text(
        out_root / "tables/day27_figure_table_readiness.csv",
        "item_id,source_artifact,output_target,readiness_status,next_action,must_not_claim\n"
        "F01,configs/minibench,docs/paper/figures/F01.png,pending,write script,real-world coverage\n"
        "F03,results/day30/tables/day15_bias_audit.csv,docs/paper/figures/F03.png,pending,write script,real LIO validation\n"
        "T01,results/day30/tables/day17_unbiased_probe_summary.csv,docs/paper/figures/T01.md,ready_for_conversion,convert,metric validation\n"
        "T02,results/day30/tables/day18_sequence_validity_summary.csv,docs/paper/figures/T02.md,ready_for_conversion,convert,robust prediction\n"
        "T03,results/day30/tables/day19_loso_selection_results.csv,docs/paper/figures/T03.md,ready_for_conversion,convert,generalized validity\n"
        "T04,results/day30/tables/day20_incremental_validity_summary.csv,docs/paper/figures/T04.md,ready_for_conversion,convert,substantive validity if failed\n"
        "T05,results/day30/tables/day21_joint_risk_comparison.csv,docs/paper/figures/T05.md,ready_for_conversion,convert,validated joint-risk detector\n"
        "T06,results/day30/tables/day22_gate_decision.csv,docs/paper/figures/T06.md,ready_for_conversion,convert,Go method result\n"
        "T07,results/day30/tables/day25_claim_boundary_for_paper.csv,docs/paper/figures/T07.md,ready_for_conversion,convert,forbidden claims as conclusions\n"
        "T08,results/day30/tables/day25_reproducibility_plan.csv,docs/paper/figures/T08.md,ready_for_conversion,convert,full real-render guarantee from smoke path\n",
    )
    for source in [
        "day17_unbiased_probe_summary.csv",
        "day18_sequence_validity_summary.csv",
        "day19_loso_selection_results.csv",
        "day20_incremental_validity_summary.csv",
        "day21_joint_risk_comparison.csv",
        "day22_gate_decision.csv",
        "day25_claim_boundary_for_paper.csv",
        "day25_reproducibility_plan.csv",
        "day15_bias_audit.csv",
    ]:
        write_text(out_root / f"tables/{source}", "col_a,col_b\nvalue,diagnostic\n")


def write_day28_config(tmp_path: Path) -> Path:
    path = tmp_path / "day28_figure_table_generation.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day25_paper_outline, day26_paper_skeleton, day27_release_cleanup]",
                "route: figure_table_generation_scripts",
                "table_items: [T01, T02, T03, T04, T05, T06, T07, T08]",
                "pending_figure_items: [F01, F03]",
                "forbidden_actions: [weak_subspace_update, estimator_method_implementation, robust_ODI_claim, fake_figure_generation, overwrite_previous_artifacts]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


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
