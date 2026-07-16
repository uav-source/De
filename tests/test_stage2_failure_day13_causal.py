from eval.stage2_failure_day13_causal import harmful_update_metrics


def test_harmful_update_requires_alignment_and_worsening():
    result = harmful_update_metrics({"applied_update_weak_signed_m": 2.0, "prior_online_weak_error_signed_m": 3.0, "online_weak_abs_error_reduction_m": -0.1})
    assert result["update_error_alignment"] == 6.0
    assert result["harmful_update_frame"] is True
    safe = harmful_update_metrics({"applied_update_weak_signed_m": -2.0, "prior_online_weak_error_signed_m": 3.0, "online_weak_abs_error_reduction_m": -0.1})
    assert safe["harmful_update_frame"] is False
