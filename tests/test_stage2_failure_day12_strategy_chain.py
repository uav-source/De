import csv
import json
import shutil
from pathlib import Path

from eval.stage2_failure_day11b_provenance import result_tree_manifest
from eval.stage2_failure_day12_input_audit import verify_day11b_v2_plot_input

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"


def _copy(tmp_path):
    target = tmp_path / RUN.name
    shutil.copytree(RUN, target)
    return target


def test_missing_runtime_strategy_fails(tmp_path):
    target = _copy(tmp_path)
    metrics = next((target / "cases").glob("*/trajectory_metrics.json"))
    value = json.loads(metrics.read_text())
    del value["strategy"]
    metrics.write_text(json.dumps(value), encoding="utf-8")
    frozen = tmp_path / "tree.txt"
    frozen.write_bytes(result_tree_manifest(tmp_path, target))
    assert verify_day11b_v2_plot_input(tmp_path, target, frozen)["strategy_chain_mismatch_count"] > 0


def test_online_method_change_fails_chain(tmp_path):
    target = _copy(tmp_path)
    online = next((target / "cases").glob("*/frame_diagnostics_online.csv"))
    with online.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or ())
        rows = list(reader)
    rows[0]["applied_strategy"] = (
        "huber_projected_gain"
        if rows[0]["applied_strategy"] == "huber_full"
        else "huber_full"
    )
    with online.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    frozen = tmp_path / "tree.txt"
    frozen.write_bytes(result_tree_manifest(tmp_path, target))
    assert verify_day11b_v2_plot_input(tmp_path, target, frozen)["DAY12_INPUT_AUDIT_PASS"] is False


def test_case_identity_change_fails_plan_chain(tmp_path):
    target = _copy(tmp_path)
    case_manifest = next((target / "cases").glob("*/case_manifest.json"))
    value = json.loads(case_manifest.read_text())
    value["sensor_seed"] = int(value["sensor_seed"]) + 1
    case_manifest.write_text(json.dumps(value), encoding="utf-8")
    frozen = tmp_path / "tree.txt"
    frozen.write_bytes(result_tree_manifest(tmp_path, target))
    audit = verify_day11b_v2_plot_input(tmp_path, target, frozen)
    assert audit["case_identity_mismatch_count"] > 0
    assert audit["DAY12_INPUT_AUDIT_PASS"] is False
