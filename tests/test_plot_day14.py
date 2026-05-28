import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/04_plot_day14.py"
REQUIRED = [
    "Fig_D14_01_spectrum_across_scenes",
    "Fig_D14_02_odi_timeline",
    "Fig_D14_03_alignment_hist",
    "Fig_D14_04_odi_vs_axis_drift_merged_and_per_sequence",
    "Fig_D14_05_metric_validity_comparison",
    "Fig_D14_06_axis_cross_error",
    "Fig_D14_07_bias_audit_summary",
]


def test_plot_day14_script_runs_and_writes_required_outputs(tmp_path):
    out_dir = tmp_path / "figures"

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--results",
            str(ROOT / "results/day14"),
            "--out",
            str(out_dir),
        ],
        cwd=str(ROOT),
        check=True,
        timeout=120,
    )

    for name in REQUIRED:
        assert (out_dir / f"{name}.png").exists()
        assert (out_dir / f"{name}.pdf").exists()

    manifest_path = out_dir / "plotting_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["input_files"]
    assert manifest["output_files"]
    assert any("merged_and_per_sequence" in item["name"] for item in manifest["figures"])
    assert any("metric_validity_comparison" in item["name"] for item in manifest["figures"])


def test_plot_script_reads_day10_csv_instead_of_hardcoding_rho():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "day10_metric_validity.csv" in source
    assert "day10_metric_validity_per_sequence.csv" in source
    assert "day10_metric_validity_loso.csv" in source
    assert "0.647276" not in source
    assert "0.897659" not in source
