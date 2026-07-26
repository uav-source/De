import os
from pathlib import Path

import pytest

from fastlio2_adapter.day6_fallback_functional_diagnostics import (
    Day6FallbackError,
    EXPECTED_AUTHORIZATION_SHA256,
    validate_authorization_archive,
)


AUTH = Path(
    os.environ.get(
        "DAY6_AUTHORIZATION_AUDIT",
        str(
            Path.home()
            / "Degen-LIO-multihyp-D5-fallback-offline-detector-"
            "determinism-remediation-audit.tar.gz"
        ),
    )
)


def test_fixed_authorization_enables_only_fallback_day6():
    result = validate_authorization_archive(AUTH)
    assert result["authorization_audit_sha256"] == EXPECTED_AUTHORIZATION_SHA256
    assert result["DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_AUTHORIZED"] is True
    assert result["REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED"] is True
    assert result["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is False
    assert result["STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS"] == "ABANDONED_AFTER_V5"


def test_missing_authorization_is_rejected(tmp_path):
    with pytest.raises(Day6FallbackError, match="missing"):
        validate_authorization_archive(tmp_path / "missing.tar.gz")
