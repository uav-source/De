import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/16_day23_route_b_pivot.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day23"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day23_script_runs_and_preserves_day18_to_day22_inputs(tmp_path):
    out_root = tmp_path / "results/day30"
    reports_root = tmp_path / "reports"
    prepare_day18_to_day22_inputs(out_root, reports_root)
    protected = snapshot_files(out_root)
    protected.update(snapshot_files(reports_root))
    config = write_day23_config(tmp_path)
    report = reports_root / "day23_route_b_pivot_report.md"

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
            "--report",
            str(report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    failures = list(csv.DictReader((out_root / "tables/day23_failure_taxonomy.csv").open()))
    claims = list(csv.DictReader((out_root / "tables/day23_claim_consolidation.csv").open()))
    candidates = list(csv.DictReader((out_root / "tables/day23_metric_redesign_candidates.csv").open()))
    benchmark = list(csv.DictReader((out_root / "tables/day23_diagnostic_benchmark_route.csv").open()))
    recommendation = list(csv.DictReader((out_root / "tables/day23_day24_recommendation.csv").open()))
    manifest = json.loads((out_root / "manifests/day23_route_b_pivot_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert {row["failure_source_day"] for row in failures} >= {"Day 18", "Day 19", "Day 20", "Day 21", "Day 22"}
    assert claim_status(claims, "ODI " + "robustly predicts drift") == "forbidden"
    assert claim_status(claims, "Degen-LIO method is ready") == "forbidden"
    assert candidates
    assert benchmark
    assert any(row["candidate_name"] == "temporal_ODI_delta" for row in candidates)
    assert any(row["route_item"] == "no method update yet" for row in benchmark)
    assert manifest["status"] == "OK"
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert "weak-subspace update implementation" not in manifest["recommended_day24_route"]
    assert "The project should not implement weak-subspace update yet." in report_text
    assert "The evidence supports a diagnostic benchmark / metric-redesign route" in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day23_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day23_config(tmp_path)),
            "--out-root",
            str(tmp_path / "missing_day30"),
            "--reports-root",
            str(tmp_path / "missing_reports"),
            "--report",
            str(tmp_path / "reports/day23_route_b_pivot_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day23 input file" in result.stderr


def prepare_day18_to_day22_inputs(out_root: Path, reports_root: Path) -> None:
    tables = out_root / "tables"
    manifests = out_root / "manifests"
    tables.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)

    write_text(
        tables / "day18_sequence_validity_summary.csv",
        "sequence_id,ODI_axis_drift_rho,best_metric_for_axis_drift\nOC-L0-S01-M1,-0.2,ODI_median\nST-L3-S01-M1,-0.1,ODI_median\n",
    )
    write_text(
        tables / "day18_within_sequence_correlations.csv",
        "sequence_id,metric_name,target_name,spearman_rho,validity_status\nOC-L0-S01-M1,ODI_median,axis_drift_rate,-0.2,valid\n",
    )
    write_json(manifests / "day18_within_sequence_manifest.json", {"status": "OK"})
    write_text(reports_root / "day18_report.md", "Day 18 complete\n")

    write_text(
        tables / "day19_grouped_metric_summary.csv",
        "metric_name,target_name,n_valid_sequences,mean_abs_rho\nODI_median,axis_drift_rate,4,0.05\n",
    )
    write_text(
        tables / "day19_loso_selection_results.csv",
        "held_out_sequence,target_name,selected_metric_from_train,held_out_validity_status\nOC-L0-S01-M1,axis_drift_rate,ODI_median,valid\n",
    )
    write_text(
        tables / "day19_metric_pass_fail_summary.csv",
        "metric_name,target_name,final_day19_status,reason\nODI_median,axis_drift_rate,exploratory_not_validated,grouped support insufficient\n",
    )
    write_json(manifests / "day19_grouped_loso_manifest.json", {"status": "OK"})
    write_text(reports_root / "day19_report.md", "Day 19 complete\n")

    write_text(
        tables / "day20_partial_correlations.csv",
        "metric_name,target_name,partial_spearman_rho,passes_effect_size\nODI_median,axis_drift_rate,0.02,false\n",
    )
    write_text(
        tables / "day20_incremental_validity_summary.csv",
        "metric_name,target_name,final_day20_status,reason\nODI_median,axis_drift_rate,exploratory_not_validated,effect_size failed\n",
    )
    write_json(manifests / "day20_controlled_partial_manifest.json", {"status": "OK"})
    write_text(reports_root / "day20_report.md", "Day 20 complete\n")

    write_text(
        tables / "day21_joint_risk_comparison.csv",
        "feature_name,target_name,final_day21_status,reason\njoint_risk_no_odi,axis_drift_rate,exploratory_not_validated,no candidate\n",
    )
    write_json(
        manifests / "day21_joint_risk_manifest.json",
        {"status": "OK", "weak_update_authorized": False},
    )
    write_text(reports_root / "day21_report.md", "Day 21 complete\n")

    write_text(
        tables / "day22_evidence_matrix.csv",
        "day,evidence_item,status\n22,gate review,NO_GO_METHOD_UPDATE\n",
    )
    write_text(
        tables / "day22_gate_decision.csv",
        "gate_name,passed,reason\nmethod_update_gate,false,blocked\nweak_update_authorization_gate,false,not authorized\n",
    )
    write_text(
        tables / "day22_claim_status.csv",
        "claim_id,claim_text,status,forbidden_wording\nC1,ODI robustly predicts drift,forbidden,do not claim\nC5,legacy toy_lio is diagnostic only,allowed,\n",
    )
    write_text(
        tables / "day22_next_action_plan.csv",
        "next_day,route,task,allowed,reason\nDay 23,Route B,metric redesign,true,selected\n",
    )
    write_json(
        manifests / "day22_gate_review_manifest.json",
        {
            "status": "OK",
            "final_decision": "NO_GO_METHOD_UPDATE",
            "method_update_authorized": False,
            "weak_update_authorized": False,
            "next_route": "Route B",
        },
    )
    write_text(reports_root / "day22_gate_review.md", "No-Go method update\n")


def write_day23_config(tmp_path: Path) -> Path:
    path = tmp_path / "day23_route_b_pivot.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day18_within_sequence, day19_grouped_loso, day20_controlled_partial, day21_joint_risk, day22_gate_review]",
                "route: Route_B",
                "route_name: metric_risk_redesign_or_diagnostic_benchmark_consolidation",
                "analysis_goals: [failure_taxonomy, claim_consolidation, metric_redesign_candidates, diagnostic_benchmark_paper_route, day24_recommendation]",
                "forbidden_actions: [weak_subspace_update, method_implementation, robust_ODI_claim, overwrite_previous_artifacts]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def claim_status(rows, claim_text: str) -> str:
    return next(row for row in rows if row["claim_text"] == claim_text)["current_status"]


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
