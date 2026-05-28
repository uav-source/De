import os
import subprocess
from pathlib import Path

from day14_test_data import prepare_minimal_day14_results, prepare_minimal_observations


ROOT = Path(__file__).resolve().parents[1]


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "DEGEN_STEP_SMOKE_TEST_NO_RENDER": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig"),
            "PYTHONUNBUFFERED": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_run_plot_day14_step_smoke_returns_zero(tmp_path):
    results_dir = prepare_minimal_day14_results(tmp_path)
    figures_out = tmp_path / "figures_out"
    stdout_log = tmp_path / "logs" / "plot.stdout.log"
    stderr_log = tmp_path / "logs" / "plot.stderr.log"

    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/run_plot_day14_step.sh"),
            str(results_dir),
            str(figures_out),
            str(stdout_log),
            str(stderr_log),
            "120",
        ],
        cwd=str(ROOT),
        env=child_env(tmp_path),
        timeout=120,
    )

    assert result.returncode == 0
    assert stdout_log.exists()
    assert stderr_log.exists()
    assert (figures_out / "plotting_manifest.json").exists()


def test_run_sensitivity_step_smoke_returns_zero(tmp_path):
    results_dir = prepare_minimal_day14_results(tmp_path)
    data_root = prepare_minimal_observations(tmp_path)
    tables_out = tmp_path / "tables_out"
    figures_out = tmp_path / "figures_out"
    stdout_log = tmp_path / "logs" / "sensitivity.stdout.log"
    stderr_log = tmp_path / "logs" / "sensitivity.stderr.log"

    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/run_sensitivity_step.sh"),
            str(results_dir),
            str(data_root),
            str(tables_out),
            str(figures_out),
            str(stdout_log),
            str(stderr_log),
            "120",
            "10",
        ],
        cwd=str(ROOT),
        env=child_env(tmp_path),
        timeout=120,
    )

    assert result.returncode == 0
    assert stdout_log.exists()
    assert stderr_log.exists()
    assert (tables_out / "day12_sensitivity_D.csv").exists()
    assert (tables_out / "day12_sensitivity_tau.csv").exists()
    assert (figures_out / "plotting_manifest.json").exists()
