import csv
import json
from pathlib import Path

from eval.stage2_failure_day8 import run_stage2_failure_day8
from eval.stage2_failure_schema import FRAME_KEY_FIELDS


ROOT = Path(__file__).resolve().parents[1]


def test_day8_quick_writes_isolated_joinable_logs_and_manifest(tmp_path):
    manifest = run_stage2_failure_day8(
        ROOT,
        "pytest_day8_quick",
        tmp_path,
    )
    output = tmp_path / "pytest_day8_quick"
    online_path = output / "frame_diagnostics_online.csv"
    gt_path = output / "frame_diagnostics_gt.csv"
    manifest_path = output / "run_manifest.json"
    summary_path = output / "day8_quick_summary.json"
    assert all(path.exists() for path in [online_path, gt_path, manifest_path, summary_path])

    with online_path.open(newline="", encoding="utf-8") as handle:
        online = list(csv.DictReader(handle))
    with gt_path.open(newline="", encoding="utf-8") as handle:
        gt = list(csv.DictReader(handle))
    keys_online = [tuple(row[name] for name in FRAME_KEY_FIELDS) for row in online]
    keys_gt = [tuple(row[name] for name in FRAME_KEY_FIELDS) for row in gt]
    assert len(online) == len(gt) == 14
    assert keys_online == keys_gt
    assert len(keys_online) == len(set(keys_online))
    assert all("gt" not in name.lower().split("_") for name in online[0])

    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written == manifest
    assert manifest["DAY8_LOGGING_PASS"] is True
    assert manifest["STAGE2_GATE"] == "INCOMPLETE"
    assert manifest["reserved_test_run_performed"] is False
    assert manifest["formal_stage2c_rerun_performed"] is False
    assert manifest["gt_used_by_online_logger"] is False
    assert manifest["historical_artifacts_unchanged"] is True
    assert manifest["logging_trajectory_equivalent"] is True
    assert manifest["logging_on_off_max_trajectory_difference"] <= 1.0e-12
    assert manifest["logging_on_off_max_covariance_difference"] <= 1.0e-12
