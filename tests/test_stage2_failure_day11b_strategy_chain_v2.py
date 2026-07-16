from eval.stage2_failure_day11b_provenance import build_strategy_chain_audit


def _audit(plan="huber_full", manifest="huber_full", metrics="huber_full",
           disabled="huber_full", enabled="huber_full", online="huber_full"):
    return build_strategy_chain_audit(
        "case", plan, manifest, {"strategy": metrics}, {"strategy": disabled},
        {"strategy": enabled}, [{"applied_strategy": online}],
    )


def test_complete_runtime_strategy_chain_passes():
    assert _audit()["pass"] is True


def test_runtime_return_mismatch_fails_chain():
    assert _audit(disabled="huber_projected_gain")["pass"] is False


def test_online_applied_strategy_mismatch_fails_chain():
    assert _audit(online="huber_projected_gain")["pass"] is False


def test_all_sources_sharing_wrong_method_still_fail_allowed_method_check():
    assert _audit(*(["made_up_strategy"] * 6))["pass"] is False


def test_oracle_and_legacy_names_are_rejected_without_aliasing():
    assert _audit(*(["huber_oracle_projected_gain"] * 6))["pass"] is False
    assert _audit(*(["axial_correspondence_slip"] * 6))["pass"] is False
