import csv
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/06_sensitivity.py"


def child_env():
    env = os.environ.copy()
    env.update(
        {
            "MPLBACKEND": "Agg",
            "PYTHONUNBUFFERED": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


@pytest.fixture(scope="module")
def sensitivity_run(tmp_path_factory):
    base = tmp_path_factory.mktemp("sensitivity")
    tables = base / "tables"
    figures = base / "figures"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(ROOT / "configs/detector/odi_default.yaml"),
            "--results",
            str(ROOT / "results/day14"),
            "--out",
            str(tables),
            "--figures-out",
            str(figures),
        ],
        cwd=str(ROOT),
        env=child_env(),
        check=True,
        timeout=120,
    )
    return {"tables": tables, "figures": figures}


def test_sensitivity_script_writes_required_tables_and_figures(sensitivity_run):
    d_path = sensitivity_run["tables"] / "day12_sensitivity_D.csv"
    tau_path = sensitivity_run["tables"] / "day12_sensitivity_tau.csv"
    assert d_path.exists()
    assert tau_path.exists()
    for name in ["Fig_D14_08_sensitivity_D", "Fig_D14_09_sensitivity_tau"]:
        assert (sensitivity_run["figures"] / f"{name}.png").exists()
        assert (sensitivity_run["figures"] / f"{name}.pdf").exists()
    manifest = json.loads((sensitivity_run["figures"] / "plotting_manifest.json").read_text(encoding="utf-8"))
    figure_names = {item["name"] for item in manifest["figures"]}
    assert "Fig_D14_08_sensitivity_D" in figure_names
    assert "Fig_D14_09_sensitivity_tau" in figure_names

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


def read_rows(path):
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
