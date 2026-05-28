import csv
import math
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/06_sensitivity.py"


def test_sensitivity_script_runs_and_writes_required_tables(tmp_path):
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(ROOT / "configs/detector/odi_default.yaml"),
            "--results",
            str(ROOT / "results/day14"),
            "--out",
            str(tmp_path),
        ],
        cwd=str(ROOT),
        check=True,
        timeout=120,
    )

    d_path = tmp_path / "day12_sensitivity_D.csv"
    tau_path = tmp_path / "day12_sensitivity_tau.csv"
    assert d_path.exists()
    assert tau_path.exists()

    d_rows = read_rows(d_path)
    tau_rows = read_rows(tau_path)
    assert len(d_rows) == 9
    assert len(tau_rows) == 4
    assert len({(row["s_theta"], row["s_p"]) for row in d_rows}) == 9
    assert len({row["tau_w"] for row in tau_rows}) == 4
    assert any(row["s_theta"] != "0.05" or row["s_p"] != "0.5" for row in d_rows)
    assert any(row["tau_w"] != "0.02" for row in tau_rows)

    required = [
        "ODI_median",
        "merged_ODI_axis_drift_spearman",
        "OC_ODI_axis_drift_spearman",
        "ST_ODI_axis_drift_spearman",
        "CT_ODI_axis_drift_spearman",
        "RT_ODI_axis_drift_spearman",
        "OC_false_reliable_ratio",
        "OC_false_high_degeneracy_ratio",
    ]
    assert any(row["valid_sensitivity_point"] == "1" for row in d_rows)
    assert any(row["valid_sensitivity_point"] == "0" for row in d_rows)
    for row in d_rows + tau_rows:
        for key in required:
            assert key in row
            if row["valid_sensitivity_point"] == "1":
                assert math.isfinite(float(row[key]))
        if row["valid_sensitivity_point"] == "0":
            assert row["notes"]


def test_sensitivity_figures_are_written_by_script(tmp_path):
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(ROOT / "configs/detector/odi_default.yaml"),
            "--results",
            str(ROOT / "results/day14"),
            "--out",
            str(tmp_path),
        ],
        cwd=str(ROOT),
        check=True,
        timeout=120,
    )

    figures = ROOT / "results/day14/figures"
    for name in ["Fig_D14_08_sensitivity_D", "Fig_D14_09_sensitivity_tau"]:
        assert (figures / f"{name}.png").exists()
        assert (figures / f"{name}.pdf").exists()


def read_rows(path):
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
