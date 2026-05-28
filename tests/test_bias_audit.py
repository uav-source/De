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

from eval.bias_audit import (
    flag_scene_family_confound,
    inspect_toy_lio_bias_config,
    summarize_bias_by_sequence,
)


SCRIPT = ROOT / "scripts/08_bias_audit.py"
TOY_LIO = ROOT / "src/minibench/toy_lio.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig"),
        }
    )
    return env


def test_inspect_toy_lio_detects_scene_family_axis_bias():
    audit = inspect_toy_lio_bias_config(TOY_LIO)

    assert audit["sample_process_noise_found"] is True
    assert audit["scene_family_dependent_axis_bias"] is True
    bias = audit["axis_bias_by_family"]
    assert bias["OC"] == 0.0
    assert bias["ST"] > bias["OC"]
    assert bias["CT"] > bias["OC"]
    assert bias["RT"] > bias["OC"]


def test_bias_summary_flags_scene_family_confound():
    audit = inspect_toy_lio_bias_config(TOY_LIO)
    toy_rows = [
        {"sequence_id": "OC-L0-S01-M1", "final_axis_error": "0.001"},
        {"sequence_id": "ST-L3-S01-M1", "final_axis_error": "5.0"},
        {"sequence_id": "CT-L2-S01-M2", "final_axis_error": "3.0"},
        {"sequence_id": "RT-L4-S01-M1", "final_axis_error": "6.0"},
    ]
    metric_rows = [
        {"sequence_id": "OC-L0-S01-M1", "ODI_median": "0.5", "axis_drift_rate_median": "0.0"},
        {"sequence_id": "ST-L3-S01-M1", "ODI_median": "0.72", "axis_drift_rate_median": "0.04"},
        {"sequence_id": "CT-L2-S01-M2", "ODI_median": "0.72", "axis_drift_rate_median": "0.03"},
        {"sequence_id": "RT-L4-S01-M1", "ODI_median": "0.73", "axis_drift_rate_median": "0.05"},
    ]

    rows = summarize_bias_by_sequence(audit, toy_rows, metric_rows)
    confound = flag_scene_family_confound(rows, audit)

    assert len(rows) == 4
    assert {row["sequence_id"] for row in rows} == {
        "OC-L0-S01-M1",
        "ST-L3-S01-M1",
        "CT-L2-S01-M2",
        "RT-L4-S01-M1",
    }
    assert next(row for row in rows if row["sequence_id"] == "RT-L4-S01-M1")["confound_risk_level"] == "HIGH"
    assert confound["confound_risk_level"] == "HIGH"
    assert confound["scene_family_axis_bias_present"] == "true"


def test_bias_audit_script_writes_csv_manifest_and_report(tmp_path):
    tables = prepare_day14_tables(tmp_path)
    day10_report = tmp_path / "reports" / "day10_report.md"
    day10_report.parent.mkdir(parents=True)
    day10_report.write_text("Merged correlation may be amplified by Day 7 scene-family axis_bias.\n", encoding="utf-8")
    toy_hash_before = TOY_LIO.read_bytes()
    day14_input_hashes = {path: path.read_bytes() for path in tables.glob("*.csv")}
    day14_input_hashes[day10_report] = day10_report.read_bytes()

    out = tmp_path / "results/day30/tables/day15_bias_audit.csv"
    manifest = tmp_path / "results/day30/manifests/day15_bias_audit_manifest.json"
    report = tmp_path / "reports/day15_report.md"
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--toy-lio",
            str(TOY_LIO),
            "--day14-tables",
            str(tables),
            "--day10-report",
            str(day10_report),
            "--out",
            str(out),
            "--manifest",
            str(manifest),
            "--report",
            str(report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    assert TOY_LIO.read_bytes() == toy_hash_before
    for path, content in day14_input_hashes.items():
        assert path.read_bytes() == content
    rows = list(csv.DictReader(out.open("r", encoding="utf-8")))
    assert rows
    assert set(rows[0]) >= {
        "sequence_id",
        "scene_family",
        "legacy_axis_bias",
        "final_axis_error",
        "ODI_median",
        "axis_drift_rate_median",
        "confound_risk_level",
        "interpretation",
    }
    assert any(row["confound_risk_level"] == "HIGH" for row in rows)

    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["status"] == "OK"
    assert manifest_data["git_commit"]
    assert manifest_data["inputs"]
    assert str(out).endswith("day15_bias_audit.csv")

    report_text = report.read_text(encoding="utf-8")
    assert "legacy toy_lio has scene-family-dependent axis_bias" in report_text
    assert "diagnostic evidence" in report_text
    assert "main evidence" in report_text


def test_bias_audit_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--toy-lio",
            str(TOY_LIO),
            "--day14-tables",
            str(tmp_path / "missing_tables"),
            "--day10-report",
            str(tmp_path / "missing_day10.md"),
            "--out",
            str(tmp_path / "out.csv"),
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--report",
            str(tmp_path / "report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day15 input file" in result.stderr


def prepare_day14_tables(tmp_path: Path) -> Path:
    tables = tmp_path / "results/day14/tables"
    tables.mkdir(parents=True)
    write_csv(
        tables / "day07_toy_lio_summary.csv",
        ["sequence_id", "final_axis_error"],
        [
            ["OC-L0-S01-M1", "0.001"],
            ["ST-L3-S01-M1", "5.0"],
            ["CT-L2-S01-M2", "3.0"],
            ["RT-L4-S01-M1", "6.0"],
        ],
    )
    write_csv(
        tables / "day08_metric_summary.csv",
        ["sequence_id", "final_axis_error", "ODI_median", "axis_drift_rate_median"],
        [
            ["OC-L0-S01-M1", "0.001", "0.5", "0.0"],
            ["ST-L3-S01-M1", "5.0", "0.72", "0.04"],
            ["CT-L2-S01-M2", "3.0", "0.72", "0.03"],
            ["RT-L4-S01-M1", "6.0", "0.73", "0.05"],
        ],
    )
    write_csv(
        tables / "day10_metric_validity.csv",
        ["scope", "metric_name", "target_name", "spearman_rho"],
        [["merged_all_sequences", "ODI", "axis_drift_rate", "0.64"]],
    )
    return tables


def write_csv(path: Path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)


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
