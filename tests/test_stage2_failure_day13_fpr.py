from eval.stage2_failure_day13_statistics import block_bootstrap_fpr


def test_fpr_geometry_block_bootstrap_uses_strict_greater_than():
    rows = [{"geometry_seed": seed, "primary_score": score} for seed in range(10) for score in (0.0, 1.0, 2.0)]
    result = block_bootstrap_fpr(rows, 1.0)
    assert result["false_positive_frame_count"] == 10
    assert result["eligible_frame_count"] == 30
    assert result["valid_bootstrap_count"] == 5000
