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


SCRIPT = ROOT / "scripts/15_day22_gate_review.py"
REQUIRED_GATES = {
    "unbiased_protocol_gate",
    "within_sequence_validation_gate",
    "grouped_loso_gate",
    "odi_controlled_validity_gate",
    "joint_risk_candidate_gate",
    "weak_update_authorization_gate",
    "method_update_gate",
}


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day22"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day22_script_runs_and_blocks_method_update_when_day21_false(tmp_path):
    out_root = tmp_path / "results/day30"
    reports_root = tmp_path / "reports"
    prepare_day15_to_day21_inputs(out_root, reports_root, weak_update_authorized=False)
    protected = snapshot_files(out_root)
    config = write_day22_config(tmp_path)
    report = reports_root / "day22_gate_review.md"

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

    evidence = list(csv.DictReader((out_root / "tables/day22_evidence_matrix.csv").open()))
    gates = list(csv.DictReader((out_root / "tables/day22_gate_decision.csv").open()))
    claims = list(csv.DictReader((out_root / "tables/day22_claim_status.csv").open()))
    plan = list(csv.DictReader((out_root / "tables/day22_next_action_plan.csv").open()))
    manifest = json.loads((out_root / "manifests/day22_gate_review_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert evidence
    assert gates
    assert claims
    assert plan
    assert REQUIRED_GATES <= {row["gate_name"] for row in gates}
    assert gate_passed(gates, "weak_update_authorization_gate") is False
    assert gate_passed(gates, "method_update_gate") is False
    assert claim_status(claims, "ODI " + "robustly predicts drift") == "forbidden"
    assert claim_status(claims, "legacy toy_lio is diagnostic only") == "allowed"
    assert route_allowed(plan, "Route B") is True
    assert manifest["status"] == "OK"
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert manifest["final_decision"] != "GO_WEAK_UPDATE"
    assert manifest["missing_artifacts"] == []
    assert "Weak-subspace update is not authorized unless the gate passes." in report_text
    assert "Day 23 must follow the route selected by the gate review." in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day22_method_gate_tracks_day21_authorization(tmp_path):
    out_root = tmp_path / "results/day30"
    reports_root = tmp_path / "reports"
    prepare_day15_to_day21_inputs(out_root, reports_root, weak_update_authorized=True, joint_candidate=True)

    run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day22_config(tmp_path)),
            "--out-root",
            str(out_root),
            "--reports-root",
            str(reports_root),
            "--report",
            str(reports_root / "day22_gate_review.md"),
        ],
        tmp_path,
    )

    manifest = json.loads((out_root / "manifests/day22_gate_review_manifest.json").read_text())
    assert manifest["method_update_authorized"] is True
    assert manifest["weak_update_authorized"] is True
    assert manifest["next_route"] == "Route A"


def test_day22_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day22_config(tmp_path)),
            "--out-root",
            str(tmp_path / "missing_day30"),
            "--reports-root",
            str(tmp_path / "missing_reports"),
            "--report",
            str(tmp_path / "reports/day22_gate_review.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day22 input file" in result.stderr


def prepare_day15_to_day21_inputs(out_root: Path, reports_root: Path, weak_update_authorized: bool, joint_candidate: bool = False) -> None:
    tables = out_root / "tables"
    manifests = out_root / "manifests"
    tables.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)

    write_text(tables / "day15_bias_audit.csv", "sequence_id,confound_risk_level\nST-L3-S01-M1,HIGH\n")
    write_json(manifests / "day15_bias_audit_manifest.json", {"status": "OK"})
    write_text(reports_root / "day15_report.md", "legacy toy_lio has scene-family-dependent axis_bias\n")

    write_text(tables / "day16_unbiased_toy_lio_summary.csv", "sequence_id,axis_bias_mode,applied_axis_bias\nST-L3-S01-M1,none,0\n")
    write_json(manifests / "day16_unbiased_toy_lio_manifest.json", {"status": "OK"})
    write_text(reports_root / "day16_report.md", "unbiased protocol established\n")

    write_text(tables / "day17_unbiased_probe_trials.csv", "sequence_id,trial_id,applied_axis_bias,is_unbiased_protocol\nST-L3-S01-M1,0,0,true\n")
    write_json(manifests / "day17_unbiased_probe_manifest.json", {"status": "OK"})
    write_text(reports_root / "day17_report.md", "exploratory only\n")

    write_text(tables / "day18_window_metrics.csv", "sequence_id,window_id,applied_axis_bias,is_unbiased_protocol\nST-L3-S01-M1,0,0,true\n")
    write_json(manifests / "day18_within_sequence_manifest.json", {"status": "OK"})
    write_text(reports_root / "day18_report.md", "within sequence complete\n")

    write_text(
        tables / "day19_metric_pass_fail_summary.csv",
        "metric_name,target_name,final_day19_status,reason\nODI_median,axis_drift_rate,exploratory_not_validated,not enough support\n",
    )
    write_json(manifests / "day19_grouped_loso_manifest.json", {"status": "OK"})
    write_text(reports_root / "day19_report.md", "grouped loso complete\n")

    write_text(
        tables / "day20_incremental_validity_summary.csv",
        "metric_name,target_name,final_day20_status,reason\nODI_median,axis_drift_rate,exploratory_not_validated,controlled screen failed\n",
    )
    write_json(manifests / "day20_controlled_partial_manifest.json", {"status": "OK"})
    write_text(reports_root / "day20_report.md", "controlled partial complete\n")

    candidate_status = "candidate_supported" if joint_candidate else "exploratory_not_validated"
    write_text(
        tables / "day21_joint_risk_comparison.csv",
        "feature_name,target_name,final_day21_status,reason\njoint_risk_no_odi,axis_drift_rate,"
        + candidate_status
        + ",test reason\n",
    )
    write_json(
        manifests / "day21_joint_risk_manifest.json",
        {"status": "OK", "weak_update_authorized": weak_update_authorized},
    )
    write_text(reports_root / "day21_report.md", "joint risk complete\n")


def write_day22_config(tmp_path: Path) -> Path:
    path = tmp_path / "day22_gate_review.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day15_bias_audit, day16_unbiased_toy_lio, day17_unbiased_probe, day18_within_sequence, day19_grouped_loso, day20_controlled_partial, day21_joint_risk]",
                "gate_rules:",
                "  require_unbiased_protocol: true",
                "  require_day18_window_validation: true",
                "  require_day19_grouped_loso: true",
                "  require_day20_controlled_validity_for_odi: false",
                "  require_day21_joint_risk_candidate_for_method: true",
                "  require_weak_update_authorized_for_method: true",
                "decision_labels: [GO_WEAK_UPDATE, CONDITIONAL_ANALYSIS_ONLY, NO_GO_METHOD_UPDATE]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def gate_passed(rows, gate_name: str) -> bool:
    return next(row for row in rows if row["gate_name"] == gate_name)["passed"] == "true"


def claim_status(rows, claim_text: str) -> str:
    return next(row for row in rows if row["claim_text"] == claim_text)["status"]


def route_allowed(rows, route: str) -> bool:
    return next(row for row in rows if row["route"] == route)["allowed"] == "true"


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
