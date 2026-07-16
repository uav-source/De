import pytest

from eval.stage2_failure_day13_statistics import block_bootstrap_auroc


def _rows():
    return [{"geometry_seed": seed, "analysis_score": score, "analysis_label": label} for seed in range(10) for score, label in ((0.0, 0), (1.0, 1))]


def test_geometry_block_bootstrap_is_complete_and_reproducible():
    first = block_bootstrap_auroc(_rows())
    second = block_bootstrap_auroc(_rows())
    assert first == second
    assert first["point_estimate"] == 1.0
    assert first["valid_bootstrap_count"] == 5000


def test_frame_bootstrap_is_rejected():
    with pytest.raises(ValueError):
        block_bootstrap_auroc(_rows(), block_field="frame_index")
