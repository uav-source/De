import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/18_day25_paper_outline.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day25"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day25_script_runs_and_preserves_day14_to_day24_inputs(tmp_path):
    day14_root = tmp_path / "results/day14"
    out_root = tmp_path / "results/day30"
    reports_root = tmp_path / "reports"
    prepare_day14_to_day24_inputs(day14_root, out_root, reports_root)
    protected = snapshot_files(day14_root)
    protected.update(snapshot_files(out_root))
    protected.update(snapshot_files(reports_root))
    config = write_day25_config(tmp_path)
    report = reports_root / "day25_paper_outline_report.md"

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
            "--report",
            str(report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    titles = list(csv.DictReader((out_root / "tables/day25_title_positioning_candidates.csv").open()))
    contributions = list(csv.DictReader((out_root / "tables/day25_contribution_map.csv").open()))
    sections = list(csv.DictReader((out_root / "tables/day25_section_outline.csv").open()))
    figures = list(csv.DictReader((out_root / "tables/day25_figure_table_plan.csv").open()))
    claims = list(csv.DictReader((out_root / "tables/day25_claim_boundary_for_paper.csv").open()))
    repro = list(csv.DictReader((out_root / "tables/day25_reproducibility_plan.csv").open()))
    reviewer = list(csv.DictReader((out_root / "tables/day25_reviewer_response_plan.csv").open()))
    recommendation = list(csv.DictReader((out_root / "tables/day25_day26_recommendation.csv").open()))
    manifest = json.loads((out_root / "manifests/day25_paper_outline_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert any("diagnostic benchmark" in row["title_candidate"].lower() for row in titles)
    assert any(row["contribution_text"] == "strict metric validity negative evidence" for row in contributions)
    section_titles = {row["section_title"] for row in sections}
    assert "Metric Validity Stress Tests" in section_titles
    assert "Go/No-Go Gate and Claim Boundary" in section_titles
    assert any("Day18" in row["proposed_caption"] or "Day18" in row["source_artifact"] for row in figures)
    assert any("Day20" in row["proposed_caption"] or "Day20" in row["source_artifact"] for row in figures)
    assert any("Day22" in row["proposed_caption"] or "Day22" in row["source_artifact"] for row in figures)
    assert claim_status(claims, "ODI " + "robustly predicts drift") == "forbidden"
    assert claim_status(claims, "Degen-LIO estimator method is validated") == "forbidden"
    commands = {row["command"] for row in repro}
    for script_name in [
        "scripts/08_bias_audit.py",
        "scripts/09_run_unbiased_toy_lio.py",
        "scripts/10_unbiased_metric_probe.py",
        "scripts/11_within_sequence_validation.py",
        "scripts/12_grouped_loso_validation.py",
        "scripts/13_controlled_partial_validity.py",
        "scripts/14_joint_risk_features.py",
        "scripts/15_day22_gate_review.py",
        "scripts/16_day23_route_b_pivot.py",
        "scripts/17_day24_diagnostic_consolidation.py",
        "scripts/18_day25_paper_outline.py",
    ]:
        assert any(script_name in command for command in commands)
    release_notes = " ".join(row["notes"] + " " + row["command"] for row in repro)
    assert ".git" in release_notes
    assert "__pycache__" in release_notes
    assert ".pytest_cache" in release_notes
    assert reviewer
    assert manifest["status"] == "OK"
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert "weak-subspace update" not in manifest["recommended_day26_route"]
    assert any("paper skeleton" in row["recommended_route"] for row in recommendation if row["allowed"] == "true")
    assert "The paper should be positioned as a diagnostic benchmark / failure-analysis contribution, not a validated Degen-LIO estimator method." in report_text
    assert "Weak-subspace update remains unauthorized." in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day25_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day25_config(tmp_path)),
            "--day14-root",
            str(tmp_path / "missing_day14"),
            "--out-root",
            str(tmp_path / "missing_day30"),
            "--reports-root",
            str(tmp_path / "missing_reports"),
            "--report",
            str(tmp_path / "reports/day25_paper_outline_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day25 input file" in result.stderr


def prepare_day14_to_day24_inputs(day14_root: Path, out_root: Path, reports_root: Path) -> None:
    for root in [day14_root / "tables", day14_root / "manifests", out_root / "tables", out_root / "manifests", reports_root]:
        root.mkdir(parents=True, exist_ok=True)

    write_json(day14_root / "manifests/day14_reproduction_manifest.json", {"status": "OK"})
    write_json(day14_root / "manifests/day14_final_manifest.json", {"decision": "CONDITIONAL GO"})
    write_text(day14_root / "tables/day14_go_nogo_gates.csv", "gate_id,status\nG1,PASS\n")
    write_text(day14_root / "tables/day14_decision_summary.csv", "decision,scientific_status\nCONDITIONAL GO,mixed\n")
    write_text(reports_root / "day14_go_nogo_report.md", "Day14\n")

    write_text(out_root / "tables/day15_bias_audit.csv", "sequence_id,confound_risk_level\nST,HIGH\n")
    write_json(out_root / "manifests/day15_bias_audit_manifest.json", {"status": "OK"})
    write_text(reports_root / "day15_report.md", "Day15\n")

    write_text(out_root / "tables/day16_unbiased_toy_lio_summary.csv", "sequence_id,axis_bias_mode,applied_axis_bias\nST,none,0\n")
    write_json(out_root / "manifests/day16_unbiased_toy_lio_manifest.json", {"status": "OK"})
    write_text(reports_root / "day16_report.md", "Day16\n")

    write_text(out_root / "tables/day17_unbiased_probe_trials.csv", "sequence_id,trial_id\nST,0\n")
    write_text(out_root / "tables/day17_unbiased_probe_summary.csv", "sequence_id,n_trials\nST,20\n")
    write_text(out_root / "tables/day17_metric_drift_correlations.csv", "metric_name,target_name\nODI_median,axis_drift_rate\n")
    write_json(out_root / "manifests/day17_unbiased_probe_manifest.json", {"status": "OK"})
    write_text(reports_root / "day17_report.md", "Day17\n")

    write_text(out_root / "tables/day18_window_metrics.csv", "sequence_id,window_id\nST,0\n")
    write_text(out_root / "tables/day18_within_sequence_correlations.csv", "sequence_id,metric_name\nST,ODI_median\n")
    write_text(out_root / "tables/day18_sequence_validity_summary.csv", "sequence_id,best_metric_for_axis_drift\nST,ODI_median\n")
    write_json(out_root / "manifests/day18_within_sequence_manifest.json", {"status": "OK"})
    write_text(reports_root / "day18_report.md", "Day18\n")

    write_text(out_root / "tables/day19_grouped_metric_summary.csv", "metric_name,target_name\nODI_median,axis_drift_rate\n")
    write_text(out_root / "tables/day19_loso_selection_results.csv", "held_out_sequence\nST\n")
    write_text(out_root / "tables/day19_metric_pass_fail_summary.csv", "metric_name,target_name,final_day19_status\nODI_median,axis_drift_rate,exploratory_not_validated\n")
    write_json(out_root / "manifests/day19_grouped_loso_manifest.json", {"status": "OK"})
    write_text(reports_root / "day19_report.md", "Day19\n")

    write_text(out_root / "tables/day20_partial_correlations.csv", "metric_name,target_name\nODI_median,axis_drift_rate\n")
    write_text(out_root / "tables/day20_incremental_validity_summary.csv", "metric_name,target_name,final_day20_status\nODI_median,axis_drift_rate,exploratory_not_validated\n")
    write_json(out_root / "manifests/day20_controlled_partial_manifest.json", {"status": "OK"})
    write_text(reports_root / "day20_report.md", "Day20\n")

    write_text(out_root / "tables/day21_joint_risk_comparison.csv", "feature_name,target_name,final_day21_status\njoint_risk_no_odi,axis_drift_rate,exploratory_not_validated\n")
    write_json(out_root / "manifests/day21_joint_risk_manifest.json", {"status": "OK", "weak_update_authorized": False})
    write_text(reports_root / "day21_report.md", "Day21\n")

    write_text(out_root / "tables/day22_claim_status.csv", "claim_text,status\nODI robustly predicts drift,forbidden\n")
    write_text(out_root / "tables/day22_gate_decision.csv", "gate_name,passed\nmethod_update_gate,false\n")
    write_text(out_root / "tables/day22_next_action_plan.csv", "next_day,route\nDay 23,Route B\n")
    write_json(out_root / "manifests/day22_gate_review_manifest.json", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
    write_text(reports_root / "day22_gate_review.md", "Day22\n")

    write_text(out_root / "tables/day23_failure_taxonomy.csv", "failure_id,failure_source_day\nF22,Day 22\n")
    write_text(out_root / "tables/day23_claim_consolidation.csv", "claim_id,claim_text,current_status\nCL03,ODI robustly predicts drift,forbidden\n")
    write_text(out_root / "tables/day23_metric_redesign_candidates.csv", "candidate_id,candidate_name\nM01,temporal_ODI_delta\n")
    write_text(out_root / "tables/day23_diagnostic_benchmark_route.csv", "route_item,description\nno method update yet,blocked\n")
    write_json(out_root / "manifests/day23_route_b_pivot_manifest.json", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
    write_text(reports_root / "day23_route_b_pivot_report.md", "Day23\n")

    write_text(out_root / "tables/day24_artifact_inventory.csv", "artifact_id,day\nA14,Day 14\n")
    write_text(out_root / "tables/day24_benchmark_protocol.csv", "protocol_step,step_name\nP01,synthetic geometry / minibench generation\n")
    write_text(out_root / "tables/day24_paper_claim_map.csv", "claim_id,claim_text,claim_status\nC24-04,ODI robustly predicts drift,forbidden\n")
    write_text(out_root / "tables/day24_reviewer_risk_register.csv", "risk_id,reviewer_attack\nR01,synthetic-only\n")
    write_text(out_root / "tables/day24_release_checklist.csv", "check_id,release_item\nK09,exclude .git from final package\n")
    write_text(out_root / "tables/day24_day25_recommendation.csv", "recommended_day,recommended_route,allowed\nDay 25,Route B1: diagnostic benchmark paper outline / figure-table plan,true\n")
    write_json(out_root / "manifests/day24_diagnostic_consolidation_manifest.json", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
    write_text(reports_root / "day24_diagnostic_consolidation_report.md", "Day24\n")


def write_day25_config(tmp_path: Path) -> Path:
    path = tmp_path / "day25_paper_outline.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day14_reproduction, day15_bias_audit, day16_unbiased_protocol, day17_unbiased_probe, day18_within_sequence, day19_grouped_loso, day20_controlled_partial, day21_joint_risk, day22_gate_review, day23_route_b_pivot, day24_diagnostic_consolidation]",
                "paper_route: diagnostic_benchmark_failure_analysis",
                "paper_goals: [title_and_positioning, contribution_map, section_outline, figure_table_plan, claim_boundary, experiment_storyline, reproducibility_plan, reviewer_response_plan, day26_recommendation]",
                "forbidden_actions: [weak_subspace_update, estimator_method_implementation, robust_ODI_claim, validated_Degen_LIO_method_claim, overwrite_previous_artifacts]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def claim_status(rows, claim_text: str) -> str:
    return next(row for row in rows if row["claim_text"] == claim_text)["status"]


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
