from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.hierarchical_statistics import block_bootstrap_spearman, paired_monotonicity  # noqa: E402


def test_bootstrap_resamples_geometry_seed_blocks_and_paired_trend():
    rows = []
    for geometry_seed in [101, 202, 303]:
        for sensor_seed in [11, 22]:
            for severity, level in enumerate(["L1", "L2", "L3", "L4"]):
                rows.append(
                    {
                        "geometry_seed": geometry_seed,
                        "sensor_seed": sensor_seed,
                        "level": level,
                        "metric": severity + geometry_seed / 10000.0,
                        "target": 2 * severity + sensor_seed / 1000.0,
                    }
                )
    result = block_bootstrap_spearman(rows, "metric", "target", repetitions=100, seed=7861)
    assert result["bootstrap_blocks"] == 3
    assert result["bootstrap_method"] == "geometry_seed_block_percentile"
    trend = paired_monotonicity(rows, "metric", ["L1", "L2", "L3", "L4"], 1)
    assert trend["monotonic_pair_rate"] == 1.0
