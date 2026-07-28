from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FROZEN_EVIDENCE_LOGS = {
    "reports/zero_perturbation_environment/environment_creation.log",
    "reports/zero_perturbation_pcl_environment/environment_creation.log",
}


def test_no_generated_data_results_or_cache_is_tracked():
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    forbidden = []
    for path in tracked:
        if path.startswith("results/"):
            forbidden.append(path)
        elif path.startswith("data/") and path != "data/.gitkeep":
            forbidden.append(path)
        elif any(token in path for token in ("__pycache__", ".pytest_cache", "mplconfig")):
            forbidden.append(path)
        elif path.endswith((".pyc", ".pyo", ".log")) and path not in FROZEN_EVIDENCE_LOGS:
            forbidden.append(path)
    assert forbidden == []
