import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/19_day26_paper_skeleton.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day26"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day26_script_runs_and_preserves_day14_to_day25_inputs(tmp_path):
    day14_root = tmp_path / "results/day14"
    out_root = tmp_path / "results/day30"
    reports_root = tmp_path / "reports"
    docs_root = tmp_path / "docs/paper"
    prepare_day14_to_day25_inputs(day14_root, out_root, reports_root)
    protected = snapshot_files(day14_root)
    protected.update(snapshot_files(out_root))
    protected.update(snapshot_files(reports_root))
    config = write_day26_config(tmp_path)
    report = reports_root / "day26_paper_skeleton_report.md"

    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
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
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    skeleton = (docs_root / "diagnostic_benchmark_paper_skeleton.md").read_text(encoding="utf-8")
    sections = list(csv.DictReader((out_root / "tables/day26_section_writing_tasks.csv").open()))
    figures = list(csv.DictReader((out_root / "tables/day26_figure_table_execution_plan.csv").open()))
    readme = list(csv.DictReader((out_root / "tables/day26_readme_scope_update_plan.csv").open()))
    cleanup = list(csv.DictReader((out_root / "tables/day26_release_cleanup_plan.csv").open()))
    recommendation = list(csv.DictReader((out_root / "tables/day26_day27_recommendation.csv").open()))
    manifest = json.loads((out_root / "manifests/day26_paper_skeleton_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert "diagnostic benchmark / failure-analysis" in skeleton
    assert "not a validated Degen-LIO estimator method" in skeleton
    assert "Forbidden Claims" in skeleton
    assert "Allowed Claims" in skeleton
    assert len(sections) >= 10
    assert any(row["section_title"] == "Metric Validity Stress Tests" for row in sections)
    assert any(row["generation_status"] == "pending" for row in figures)
    assert any(row["generation_status"] == "source_available" for row in figures)
    assert any("smoke" in row["readme_section"].lower() or "smoke" in row["required_update"].lower() for row in readme)
    patterns = {row["path_or_pattern"] for row in cleanup}
    assert ".git" in patterns
    assert ".pytest_cache" in patterns
    assert "__pycache__" in patterns
    assert manifest["status"] == "OK"
    assert manifest["paper_skeleton_created"] is True
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert "weak-subspace update" not in manifest["recommended_day27_route"]
    assert any("README/release cleanup" in row["recommended_route"] for row in recommendation if row["allowed"] == "true")
    assert "The project remains a diagnostic benchmark package, not a validated Degen-LIO estimator method." in report_text
    assert "Weak-subspace update remains unauthorized." in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day26_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day26_config(tmp_path)),
            "--day14-root",
            str(tmp_path / "missing_day14"),
            "--out-root",
            str(tmp_path / "missing_day30"),
            "--reports-root",
            str(tmp_path / "missing_reports"),
            "--docs-root",
            str(tmp_path / "docs/paper"),
            "--report",
            str(tmp_path / "reports/day26_paper_skeleton_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day26 input file" in result.stderr


def prepare_day14_to_day25_inputs(day14_root: Path, out_root: Path, reports_root: Path) -> None:
    for root in [day14_root / "manifests", out_root / "tables", out_root / "manifests", reports_root]:
        root.mkdir(parents=True, exist_ok=True)
    write_json(day14_root / "manifests/day14_reproduction_manifest.json", {"status": "OK"})
    write_json(day14_root / "manifests/day14_final_manifest.json", {"decision": "CONDITIONAL GO"})
    for day in range(14, 26):
        report_name = "day14_go_nogo_report.md" if day == 14 else f"day{day}_report.md"
        if day == 22:
            report_name = "day22_gate_review.md"
        if day == 23:
            report_name = "day23_route_b_pivot_report.md"
        if day == 24:
            report_name = "day24_diagnostic_consolidation_report.md"
        if day == 25:
            report_name = "day25_paper_outline_report.md"
        write_text(reports_root / report_name, f"Day {day}\n")
    manifest_names = {
        15: "day15_bias_audit_manifest.json",
        16: "day16_unbiased_toy_lio_manifest.json",
        17: "day17_unbiased_probe_manifest.json",
        18: "day18_within_sequence_manifest.json",
        19: "day19_grouped_loso_manifest.json",
        20: "day20_controlled_partial_manifest.json",
        21: "day21_joint_risk_manifest.json",
        22: "day22_gate_review_manifest.json",
        23: "day23_route_b_pivot_manifest.json",
        24: "day24_diagnostic_consolidation_manifest.json",
        25: "day25_paper_outline_manifest.json",
    }
    for day, name in manifest_names.items():
        data = {"status": "OK"}
        if day in {21, 22, 23, 24, 25}:
            data.update({"method_update_authorized": False, "weak_update_authorized": False})
        write_json(out_root / f"manifests/{name}", data)
    write_text(
        out_root / "tables/day25_title_positioning_candidates.csv",
        "candidate_id,title_candidate,paper_type,positioning,strength,main_risk,recommended,reason\nT01,A Diagnostic Benchmark for LIO Degeneracy,diagnostic benchmark,diagnostic,scope,risk,true,best\n",
    )
    write_text(
        out_root / "tables/day25_contribution_map.csv",
        "contribution_id,contribution_text,claim_status,supporting_evidence,blocking_evidence,paper_section,risk_level,allowed_wording\nC01,strict metric validity negative evidence,allowed,Day18-21,none,Metric Validity,high,negative evidence is informative\n",
    )
    write_text(
        out_root / "tables/day25_section_outline.csv",
        "section_id,section_title,section_goal,key_points,required_evidence,figures_tables,claim_boundary,writing_risk\n"
        "S01,Introduction,position,scope,Day14,F01,diagnostic only,overclaim\n"
        "S02,Related Work,context,related work,prior work,none,diagnostic only,citation risk\n"
        "S03,Problem Formulation and Diagnostic Objective,define problem,pose block,Day6,T00,diagnostic only,method drift\n"
        "S04,Synthetic Degeneracy Benchmark,benchmark,scenes,Day14,F01,synthetic only,synthetic attack\n"
        "S05,Whitened Information and Weak-Direction Diagnostics,diagnose,weak direction,Day9,F02,not drift proof,metric overclaim\n"
        "S06,Bias Audit and Unbiased Toy Probe,audit,bias,Day15-17,F03,toy probe only,toy attack\n"
        "S07,Metric Validity Stress Tests,stress tests,negative results,Day18-21,T02-T05,negative evidence,hide failures\n"
        "S08,Go/No-Go Gate and Claim Boundary,gate,no go,Day22,T06,method blocked,overclaim\n"
        "S09,Discussion and Limitations,discuss,limits,Day24,Table R1,limitations,scope risk\n"
        "S10,Reproducibility Package,repro,commands,Day24,T08,scope,package risk\n"
        "S11,Conclusion,conclude,boundaries,Day25,none,no method claim,overclaim\n",
    )
    write_text(
        out_root / "tables/day25_figure_table_plan.csv",
        "item_id,item_type,proposed_caption,source_artifact,purpose,must_show,must_not_claim,paper_section,priority\n"
        "F01,figure,Benchmark geometry overview,configs/minibench,overview,scenes,real coverage,Benchmark,high\n"
        "T02,table,Day18 within-sequence validation,results/day30/tables/day18_sequence_validity_summary.csv,validation,weak rho,robust prediction,Metric Validity,high\n"
        "T04,table,Day20 controlled partial validity,results/day30/tables/day20_incremental_validity_summary.csv,controlled,small rho,validity if failed,Metric Validity,high\n"
        "T06,table,Day22 gate decision,results/day30/tables/day22_gate_decision.csv,gate,no go,go method,Gate,high\n",
    )
    write_text(
        out_root / "tables/day25_experiment_storyline.csv",
        "story_step,question,experiment_or_analysis,evidence_artifact,observed_result,interpretation,next_step,claim_allowed\nE01,Q,A,artifact,result,interp,next,allowed\n",
    )
    write_text(
        out_root / "tables/day25_claim_boundary_for_paper.csv",
        "claim_id,claim_text,status,allowed_wording,forbidden_wording,where_to_use,where_to_avoid,evidence_basis\n"
        "CB01,ODI robustly predicts drift,forbidden,exploratory only,do not claim,nowhere,abstract,Day20\n"
        "CB03,Degen-LIO estimator method is validated,forbidden,not validated,do not claim,limitations,title,Day22\n"
        "CB05,diagnostic benchmark is reproducible,conditional,reproducible under scripts,do not overstate,artifact,method validation,Day24\n",
    )
    write_text(
        out_root / "tables/day25_reproducibility_plan.csv",
        "repro_step,command,expected_outputs,required_inputs,runtime_expectation,notes\nR00,python3 scripts/check_env.py,status,repo,seconds,env\n",
    )
    write_text(
        out_root / "tables/day25_reviewer_response_plan.csv",
        "risk_id,reviewer_attack,short_response,evidence_to_cite,remaining_limitation,planned_mitigation\nRR01,synthetic-only,scope it,Day24,limited,add later\n",
    )
    write_text(
        out_root / "tables/day25_day26_recommendation.csv",
        "recommended_day,recommended_route,task,allowed,reason,blocking_condition\nDay 26,paper skeleton drafting,draft,true,ready,boundary\n",
    )


def write_day26_config(tmp_path: Path) -> Path:
    path = tmp_path / "day26_paper_skeleton.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day14_reproduction, day15_bias_audit, day16_unbiased_protocol, day17_unbiased_probe, day18_within_sequence, day19_grouped_loso, day20_controlled_partial, day21_joint_risk, day22_gate_review, day23_route_b_pivot, day24_diagnostic_consolidation, day25_paper_outline]",
                "paper_route: diagnostic_benchmark_failure_analysis",
                "day26_goals: [paper_skeleton_markdown, section_writing_tasks, figure_table_execution_plan, readme_scope_update_plan, release_cleanup_plan, day27_recommendation]",
                "forbidden_actions: [weak_subspace_update, estimator_method_implementation, robust_ODI_claim, validated_Degen_LIO_method_claim, overwrite_previous_artifacts]",
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
