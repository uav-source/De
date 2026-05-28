import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/17_day24_diagnostic_consolidation.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day24"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day24_script_runs_and_preserves_day14_to_day23_inputs(tmp_path):
    day14_root = tmp_path / "results/day14"
    out_root = tmp_path / "results/day30"
    reports_root = tmp_path / "reports"
    prepare_day14_to_day23_inputs(day14_root, out_root, reports_root)
    protected = snapshot_files(day14_root)
    protected.update(snapshot_files(out_root))
    protected.update(snapshot_files(reports_root))
    config = write_day24_config(tmp_path)
    report = reports_root / "day24_diagnostic_consolidation_report.md"

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

    inventory = list(csv.DictReader((out_root / "tables/day24_artifact_inventory.csv").open()))
    protocol = list(csv.DictReader((out_root / "tables/day24_benchmark_protocol.csv").open()))
    claims = list(csv.DictReader((out_root / "tables/day24_paper_claim_map.csv").open()))
    risks = list(csv.DictReader((out_root / "tables/day24_reviewer_risk_register.csv").open()))
    checklist = list(csv.DictReader((out_root / "tables/day24_release_checklist.csv").open()))
    recommendation = list(csv.DictReader((out_root / "tables/day24_day25_recommendation.csv").open()))
    manifest = json.loads((out_root / "manifests/day24_diagnostic_consolidation_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert {row["day"] for row in inventory} >= {
        "Day 14",
        "Day 15",
        "Day 16",
        "Day 17",
        "Day 18",
        "Day 19",
        "Day 20",
        "Day 21",
        "Day 22",
        "Day 23",
    }
    assert any(row["step_name"] == "Route B pivot" for row in protocol)
    assert claim_status(claims, "ODI " + "robustly predicts drift") == "forbidden"
    assert claim_status(claims, "Degen-LIO estimator update is ready") == "forbidden"
    assert risks
    release_items = {row["release_item"] for row in checklist}
    assert "exclude .git from final package" in release_items
    assert "exclude __pycache__ from final package" in release_items
    assert "exclude .pytest_cache from final package" in release_items
    assert manifest["status"] == "OK"
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert "weak-subspace update" not in manifest["recommended_day25_route"]
    assert any("paper outline" in row["recommended_route"] for row in recommendation if row["allowed"] == "true")
    assert "The current evidence supports a reproducible diagnostic package with explicit claim boundaries, not a validated Degen-LIO estimator method." in report_text
    assert "The project still should not implement weak-subspace update." in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day24_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day24_config(tmp_path)),
            "--day14-root",
            str(tmp_path / "missing_day14"),
            "--out-root",
            str(tmp_path / "missing_day30"),
            "--reports-root",
            str(tmp_path / "missing_reports"),
            "--report",
            str(tmp_path / "reports/day24_diagnostic_consolidation_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day24 input file" in result.stderr


def prepare_day14_to_day23_inputs(day14_root: Path, out_root: Path, reports_root: Path) -> None:
    for root in [day14_root / "tables", day14_root / "manifests", out_root / "tables", out_root / "manifests", reports_root]:
        root.mkdir(parents=True, exist_ok=True)

    write_json(day14_root / "manifests/day14_reproduction_manifest.json", {"status": "OK", "plot_mode": "smoke"})
    write_json(day14_root / "manifests/day14_final_manifest.json", {"decision": "CONDITIONAL GO"})
    write_text(day14_root / "tables/day14_go_nogo_gates.csv", "gate_id,status\nG1,PASS\n")
    write_text(day14_root / "tables/day14_decision_summary.csv", "decision,scientific_status\nCONDITIONAL GO,mixed\n")
    write_text(reports_root / "day14_go_nogo_report.md", "Conditional diagnostic gate\n")

    write_text(out_root / "tables/day15_bias_audit.csv", "sequence_id,confound_risk_level\nST,HIGH\n")
    write_json(out_root / "manifests/day15_bias_audit_manifest.json", {"status": "OK"})
    write_text(reports_root / "day15_report.md", "Day 15\n")

    write_text(out_root / "tables/day16_unbiased_toy_lio_summary.csv", "sequence_id,axis_bias_mode,applied_axis_bias\nST,none,0\n")
    write_json(out_root / "manifests/day16_unbiased_toy_lio_manifest.json", {"status": "OK"})
    write_text(reports_root / "day16_report.md", "Day 16\n")

    write_text(out_root / "tables/day17_unbiased_probe_trials.csv", "sequence_id,trial_id,applied_axis_bias\nST,0,0\n")
    write_text(out_root / "tables/day17_unbiased_probe_summary.csv", "sequence_id,n_trials\nST,20\n")
    write_text(out_root / "tables/day17_metric_drift_correlations.csv", "metric_name,target_name,spearman_rho\nODI_median,axis_drift_rate,0.1\n")
    write_json(out_root / "manifests/day17_unbiased_probe_manifest.json", {"status": "OK"})
    write_text(reports_root / "day17_report.md", "Day 17\n")

    write_text(out_root / "tables/day18_window_metrics.csv", "sequence_id,window_id,ODI_median\nST,0,0.8\n")
    write_text(out_root / "tables/day18_within_sequence_correlations.csv", "sequence_id,metric_name,target_name,spearman_rho\nST,ODI_median,axis_drift_rate,0.05\n")
    write_text(out_root / "tables/day18_sequence_validity_summary.csv", "sequence_id,best_metric_for_axis_drift\nST,ODI_median\n")
    write_json(out_root / "manifests/day18_within_sequence_manifest.json", {"status": "OK"})
    write_text(reports_root / "day18_report.md", "Day 18\n")

    write_text(out_root / "tables/day19_grouped_metric_summary.csv", "metric_name,target_name,n_valid_sequences\nODI_median,axis_drift_rate,3\n")
    write_text(out_root / "tables/day19_loso_selection_results.csv", "held_out_sequence,held_out_validity_status\nST,valid\n")
    write_text(out_root / "tables/day19_metric_pass_fail_summary.csv", "metric_name,target_name,final_day19_status,reason\nODI_median,axis_drift_rate,exploratory_not_validated,weak\n")
    write_json(out_root / "manifests/day19_grouped_loso_manifest.json", {"status": "OK"})
    write_text(reports_root / "day19_report.md", "Day 19\n")

    write_text(out_root / "tables/day20_partial_correlations.csv", "metric_name,target_name,partial_spearman_rho\nODI_median,axis_drift_rate,0.01\n")
    write_text(out_root / "tables/day20_incremental_validity_summary.csv", "metric_name,target_name,final_day20_status,reason\nODI_median,axis_drift_rate,exploratory_not_validated,small rho\n")
    write_json(out_root / "manifests/day20_controlled_partial_manifest.json", {"status": "OK"})
    write_text(reports_root / "day20_report.md", "Day 20\n")

    write_text(out_root / "tables/day21_joint_risk_comparison.csv", "feature_name,target_name,final_day21_status\njoint_risk_no_odi,axis_drift_rate,exploratory_not_validated\n")
    write_json(out_root / "manifests/day21_joint_risk_manifest.json", {"status": "OK", "weak_update_authorized": False})
    write_text(reports_root / "day21_report.md", "Day 21\n")

    write_text(out_root / "tables/day22_evidence_matrix.csv", "day,evidence_item,status\n22,gate,NO_GO_METHOD_UPDATE\n")
    write_text(out_root / "tables/day22_gate_decision.csv", "gate_name,passed\nmethod_update_gate,false\n")
    write_text(out_root / "tables/day22_claim_status.csv", "claim_id,claim_text,status,forbidden_wording\nC1,ODI robustly predicts drift,forbidden,do not claim\n")
    write_text(out_root / "tables/day22_next_action_plan.csv", "next_day,route,allowed\nDay 23,Route B,true\n")
    write_json(out_root / "manifests/day22_gate_review_manifest.json", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
    write_text(reports_root / "day22_gate_review.md", "Day 22\n")

    write_text(out_root / "tables/day23_failure_taxonomy.csv", "failure_id,failure_source_day\nF22,Day 22\n")
    write_text(out_root / "tables/day23_claim_consolidation.csv", "claim_id,claim_text,current_status\nCL03,ODI robustly predicts drift,forbidden\n")
    write_text(out_root / "tables/day23_metric_redesign_candidates.csv", "candidate_id,candidate_name\nM01,temporal_ODI_delta\n")
    write_text(out_root / "tables/day23_diagnostic_benchmark_route.csv", "route_item,description\nno method update yet,blocked\n")
    write_text(out_root / "tables/day23_day24_recommendation.csv", "recommended_day,recommended_route,allowed\nDay 24,diagnostic benchmark consolidation,true\n")
    write_json(out_root / "manifests/day23_route_b_pivot_manifest.json", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
    write_text(reports_root / "day23_route_b_pivot_report.md", "Day 23\n")


def write_day24_config(tmp_path: Path) -> Path:
    path = tmp_path / "day24_diagnostic_consolidation.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day14_reproduction, day15_bias_audit, day16_unbiased_protocol, day17_unbiased_probe, day18_within_sequence, day19_grouped_loso, day20_controlled_partial, day21_joint_risk, day22_gate_review, day23_route_b_pivot]",
                "route: diagnostic_benchmark_consolidation",
                "consolidation_goals: [artifact_inventory, benchmark_protocol, paper_claim_map, reviewer_risk_register, release_checklist, day25_recommendation]",
                "forbidden_actions: [weak_subspace_update, estimator_method_implementation, robust_ODI_claim, overwrite_previous_artifacts]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def claim_status(rows, claim_text: str) -> str:
    return next(row for row in rows if row["claim_text"] == claim_text)["claim_status"]


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
