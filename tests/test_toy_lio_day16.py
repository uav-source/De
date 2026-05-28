import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.toy_lio import resolve_axis_bias, run_toy_lio  # noqa: E402


SCRIPT = ROOT / "scripts/09_run_unbiased_toy_lio.py"
UNBIASED_CONFIG = ROOT / "configs/toy_lio/unbiased_day16.yaml"
DETECTOR_CONFIG = ROOT / "configs/detector/odi_default.yaml"
SEQUENCES = ["OC-L0-S01-M1", "ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1"]


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day16"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_axis_bias_modes_are_explicit():
    assert resolve_axis_bias("OC", {"axis_bias_mode": "legacy_scene_family"}) == 0.0
    assert resolve_axis_bias("ST", {"axis_bias_mode": "legacy_scene_family"}) == 0.022
    assert resolve_axis_bias("CT", {"axis_bias_mode": "legacy_scene_family"}) == 0.016
    assert resolve_axis_bias("RT", {"axis_bias_mode": "legacy_scene_family"}) == 0.026

    for family in ["OC", "ST", "CT", "RT"]:
        assert resolve_axis_bias(family, {"axis_bias_mode": "none"}) == 0.0

    assert resolve_axis_bias("RT", {"axis_bias_mode": "controlled", "controlled_axis_bias": 0.123}) == 0.123
    assert resolve_axis_bias("ST", {"axis_bias_mode": "controlled", "controlled_axis_bias": {"ST": 0.007}}) == 0.007
    with pytest.raises(ValueError, match="explicitly define"):
        resolve_axis_bias("CT", {"axis_bias_mode": "controlled", "controlled_axis_bias": {"ST": 0.007}})


def test_unbiased_run_applies_zero_axis_bias(day14_tmp_pipeline):
    result = run_toy_lio(
        day14_tmp_pipeline["seq"]("RT-L4-S01-M1"),
        DETECTOR_CONFIG,
        UNBIASED_CONFIG,
    )

    metadata = result["bias_metadata"]
    assert metadata["axis_bias_mode"] == "none"
    assert metadata["perturbation_profile"] == "unbiased_day16"
    assert metadata["applied_axis_bias"] == 0.0
    assert metadata["is_unbiased_protocol"] is True


def test_day16_script_runs_and_preserves_day14_inputs(tmp_path, day14_tmp_pipeline):
    day14_results = prepare_day14_inputs(tmp_path)
    out_root = tmp_path / "results/day30"
    prepare_day15_inputs(out_root)
    protected = snapshot_files(day14_results)
    protected.update(snapshot_files(out_root))

    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(UNBIASED_CONFIG),
            "--detector-config",
            str(DETECTOR_CONFIG),
            "--data-root",
            str(day14_tmp_pipeline["data_root"]),
            "--day14-results",
            str(day14_results),
            "--out-root",
            str(out_root),
            "--report",
            str(tmp_path / "reports/day16_report.md"),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    summary_path = out_root / "tables/day16_unbiased_toy_lio_summary.csv"
    manifest_path = out_root / "manifests/day16_unbiased_toy_lio_manifest.json"
    report_path = tmp_path / "reports/day16_report.md"
    assert summary_path.exists()
    assert manifest_path.exists()
    assert report_path.exists()

    rows = list(csv.DictReader(summary_path.open("r", encoding="utf-8")))
    assert len(rows) == 4
    assert {row["axis_bias_mode"] for row in rows} == {"none"}
    assert {row["applied_axis_bias"] for row in rows} == {"0"}
    assert {row["is_unbiased_protocol"] for row in rows} == {"true"}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "OK"
    assert manifest["axis_bias_mode"] == "none"
    assert manifest["perturbation_profile"] == "unbiased_day16"
    assert manifest["legacy_behavior_preserved"] is True
    assert manifest["unbiased_protocol_passed"] is True
    assert manifest["missing_artifacts"] == []

    report = report_path.read_text(encoding="utf-8")
    assert "Day 16 establishes an unbiased toy_lio protocol, but does not yet validate ODI." in report
    assert "ODI robustly predicts drift" not in report


def test_day16_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(UNBIASED_CONFIG),
            "--data-root",
            str(tmp_path / "missing_data"),
            "--day14-results",
            str(tmp_path / "missing_day14"),
            "--out-root",
            str(tmp_path / "results/day30"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day16 input file" in result.stderr


def prepare_day14_inputs(tmp_path: Path) -> Path:
    results = tmp_path / "results/day14"
    raw = results / "raw"
    tables = results / "tables"
    raw.mkdir(parents=True)
    tables.mkdir(parents=True)
    for idx, sequence_id in enumerate(SEQUENCES):
        write_odi(raw / f"{sequence_id}_odi.csv", offset=idx)
    write_text_csv(tables / "day10_metric_validity_per_sequence.csv", "sequence_id,metric_name,target_name,spearman_rho\nST-L3-S01-M1,ODI,axis_drift_rate,-0.1\n")
    write_text_csv(tables / "day10_metric_validity_loso.csv", "held_out_sequence,metric_name,target_name,test_spearman_rho_or_auc\nST-L3-S01-M1,ODI,axis_drift_rate,-0.1\n")
    return results


def prepare_day15_inputs(out_root: Path) -> None:
    (out_root / "tables").mkdir(parents=True, exist_ok=True)
    (out_root / "manifests").mkdir(parents=True, exist_ok=True)
    write_text_csv(out_root / "tables/day15_bias_audit.csv", "sequence_id,confound_risk_level\nST-L3-S01-M1,HIGH\n")
    (out_root / "manifests/day15_bias_audit_manifest.json").write_text('{"status":"OK"}\n', encoding="utf-8")


def write_odi(path: Path, offset: int) -> None:
    fieldnames = ["timestamp", "ODI", "AIS", "lambda_min_clamped", "condition_number"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx in range(5):
            writer.writerow(
                {
                    "timestamp": idx,
                    "ODI": 0.5 + 0.01 * offset,
                    "AIS": 7.0 + offset,
                    "lambda_min_clamped": 0.1 * offset,
                    "condition_number": 100.0 + offset,
                }
            )


def write_text_csv(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


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
