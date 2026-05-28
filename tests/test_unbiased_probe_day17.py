import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.unbiased_probe import build_trial_schedule, validate_no_scene_family_bias  # noqa: E402


SCRIPT = ROOT / "scripts/10_unbiased_metric_probe.py"
DAY17_CONFIG = ROOT / "configs/toy_lio/unbiased_day17.yaml"
DETECTOR_CONFIG = ROOT / "configs/detector/odi_default.yaml"
SEQUENCES = ["OC-L0-S01-M1", "ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1"]
METRICS = {"ODI_median", "AIS_median", "lambda_min_clamped_median", "condition_number_median"}


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day17"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day17_schedule_uses_twenty_trials_from_config():
    config = yaml.safe_load(DAY17_CONFIG.read_text(encoding="utf-8"))
    schedule = build_trial_schedule(config)

    assert len(schedule) == 80
    for sequence_id in SEQUENCES:
        seq_rows = [row for row in schedule if row["sequence_id"] == sequence_id]
        assert len(seq_rows) == 20
        assert [row["trial_id"] for row in seq_rows] == list(range(20))
        assert seq_rows[0]["seed"] == 17000
        assert seq_rows[1]["seed"] == 17037


def test_validate_no_scene_family_bias_requires_zero_bias():
    rows = [
        {"axis_bias_mode": "none", "applied_axis_bias": "0", "is_unbiased_protocol": "true"},
        {"axis_bias_mode": "none", "applied_axis_bias": "0", "is_unbiased_protocol": "true"},
    ]
    assert validate_no_scene_family_bias(rows)
    rows[1]["applied_axis_bias"] = "0.1"
    assert not validate_no_scene_family_bias(rows)


def test_day17_script_runs_and_preserves_day14_day15_day16_inputs(tmp_path, day14_tmp_pipeline):
    config = tmp_path / "unbiased_day17_small.yaml"
    config.write_text(
        "\n".join(
            [
                "axis_bias_mode: none",
                "perturbation_profile: unbiased_day17",
                "n_trials: 2",
                "seed: 17000",
                "seed_stride: 37",
                "notes: test config",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    day14_results = prepare_day14_inputs(tmp_path)
    out_root = tmp_path / "results/day30"
    prepare_day15_day16_inputs(out_root)
    protected = snapshot_files(day14_results)
    protected.update(snapshot_files(out_root))
    report = tmp_path / "reports/day17_report.md"

    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
            "--detector-config",
            str(DETECTOR_CONFIG),
            "--data-root",
            str(day14_tmp_pipeline["data_root"]),
            "--day14-results",
            str(day14_results),
            "--out-root",
            str(out_root),
            "--report",
            str(report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    trials = list(csv.DictReader((out_root / "tables/day17_unbiased_probe_trials.csv").open()))
    summary = list(csv.DictReader((out_root / "tables/day17_unbiased_probe_summary.csv").open()))
    correlations = list(csv.DictReader((out_root / "tables/day17_metric_drift_correlations.csv").open()))
    manifest = json.loads((out_root / "manifests/day17_unbiased_probe_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert len(trials) == 8
    for sequence_id in SEQUENCES:
        assert sum(row["sequence_id"] == sequence_id for row in trials) == 2
    assert {row["axis_bias_mode"] for row in trials} == {"none"}
    assert {row["applied_axis_bias"] for row in trials} == {"0"}
    assert {row["is_unbiased_protocol"] for row in trials} == {"true"}
    assert len(summary) == 4
    assert {row["metric_name"] for row in correlations} >= METRICS
    assert {"merged", "per_scene_family"} <= {row["scope"] for row in correlations}
    assert manifest["status"] == "OK"
    assert manifest["row_count"] == 8
    assert manifest["unbiased_protocol_passed"] is True
    assert manifest["no_scene_family_bias_passed"] is True
    assert manifest["missing_artifacts"] == []
    assert "Day 17 does not yet validate ODI." in report_text
    assert "Day 18 must perform stricter within-sequence validation" in report_text
    assert "ODI robustly predicts drift" not in report_text


def test_day17_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(DAY17_CONFIG),
            "--data-root",
            str(tmp_path / "missing_data"),
            "--day14-results",
            str(tmp_path / "missing_day14"),
            "--out-root",
            str(tmp_path / "results/day30"),
            "--report",
            str(tmp_path / "reports/day17_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day17 input file" in result.stderr


def prepare_day14_inputs(tmp_path: Path) -> Path:
    results = tmp_path / "results/day14"
    raw = results / "raw"
    tables = results / "tables"
    raw.mkdir(parents=True)
    tables.mkdir(parents=True)
    for idx, sequence_id in enumerate(SEQUENCES):
        write_odi(raw / f"{sequence_id}_odi.csv", offset=idx)
    write_text(tables / "day10_metric_validity_per_sequence.csv", "sequence_id,metric_name,target_name,spearman_rho\nST-L3-S01-M1,ODI,axis_drift_rate,-0.1\n")
    write_text(tables / "day10_metric_validity_loso.csv", "held_out_sequence,metric_name,target_name,test_spearman_rho_or_auc\nST-L3-S01-M1,ODI,axis_drift_rate,-0.1\n")
    return results


def prepare_day15_day16_inputs(out_root: Path) -> None:
    (out_root / "tables").mkdir(parents=True, exist_ok=True)
    (out_root / "manifests").mkdir(parents=True, exist_ok=True)
    write_text(out_root / "tables/day15_bias_audit.csv", "sequence_id,confound_risk_level\nST-L3-S01-M1,HIGH\n")
    write_text(out_root / "manifests/day15_bias_audit_manifest.json", '{"status":"OK"}\n')
    write_text(out_root / "tables/day16_unbiased_toy_lio_summary.csv", "sequence_id,axis_bias_mode,applied_axis_bias\nST-L3-S01-M1,none,0\n")
    write_text(out_root / "manifests/day16_unbiased_toy_lio_manifest.json", '{"status":"OK"}\n')


def write_odi(path: Path, offset: int) -> None:
    fieldnames = ["timestamp", "ODI", "AIS", "lambda_min_clamped", "condition_number", "axis_alignment"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx in range(6):
            writer.writerow(
                {
                    "timestamp": idx,
                    "ODI": 0.5 + 0.05 * offset,
                    "AIS": 9.0 - offset,
                    "lambda_min_clamped": 100.0 if offset == 0 else 0.0,
                    "condition_number": 100.0 + 1000.0 * offset,
                    "axis_alignment": "" if offset == 0 else 1.0,
                }
            )


def write_text(path: Path, text: str) -> None:
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
