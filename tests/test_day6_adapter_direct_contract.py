from fastlio2_adapter.contract_aware_direct_comparison import (
    ADAPTER_PRECONDITION_DOMAIN,
    PRODUCTION_EXECUTED_DOMAIN,
)


def test_two_explicit_equivalence_domains_remain_distinct():
    assert PRODUCTION_EXECUTED_DOMAIN != ADAPTER_PRECONDITION_DOMAIN
    assert PRODUCTION_EXECUTED_DOMAIN == "PRODUCTION_EXECUTED_DOMAIN"
    assert ADAPTER_PRECONDITION_DOMAIN == "ADAPTER_PRECONDITION_DOMAIN"


def test_adapter_guard_is_still_rows_less_than_columns():
    from fastlio2_adapter import detector_adapter

    source = open(detector_adapter.__file__, encoding="utf-8").read()
    assert "if jacobian.shape[0] < jacobian.shape[1]:" in source
    assert 'invalid_reason="TOO_FEW_CORRESPONDENCES"' in source
