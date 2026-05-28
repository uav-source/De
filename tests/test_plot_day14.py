import json
import os
import subprocess
import sys
from pathlib import Path

from day14_test_data import prepare_minimal_day14_results


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


def child_env(mpl_config_dir: Path):
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(mpl_config_dir),
            "PYTHONUNBUFFERED": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def run_with_diagnostics(cmd, *, cwd: Path, env: dict, timeout: int) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"subprocess timed out after {timeout}s: {' '.join(map(str, cmd))}")
        print_tail("stdout", exc.stdout)
        print_tail("stderr", exc.stderr)
        raise
    if result.returncode != 0:
        print(f"subprocess failed with return code {result.returncode}: {' '.join(map(str, cmd))}")
        print_tail("stdout", result.stdout)
        print_tail("stderr", result.stderr)
    result.check_returncode()
    return result


def print_tail(label: str, content) -> None:
    if content is None:
        print(f"--- {label} empty ---")
        return
    if isinstance(content, bytes):
        content = content.decode(errors="replace")
    lines = str(content).splitlines()
    print(f"--- {label} last {min(100, len(lines))} lines ---")
    for line in lines[-100:]:
        print(line)


def test_plot_day14_script_runs_and_writes_required_outputs(tmp_path):
    results_dir = prepare_minimal_day14_results(tmp_path)
    out_dir = tmp_path / "plot_outputs"

    run_with_diagnostics(
        [
            sys.executable,
            str(SCRIPT),
            "--results",
            str(results_dir),
            "--out",
            str(out_dir),
            "--smoke-test-no-render",
        ],
        cwd=ROOT,
        env=child_env(tmp_path / "mplconfig_plot"),
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
