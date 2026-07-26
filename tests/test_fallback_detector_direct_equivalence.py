import pytest

from fastlio2_adapter.offline_detector_determinism import (
    compare_direct_production,
    direct_production_metrics,
    evaluate_frozen_observation,
)
from test_runtime_observation_v3 import v3_record


def test_offline_adapter_matches_direct_production_detector():
    record = v3_record()
    output = evaluate_frozen_observation(record, record_index=0)
    direct = direct_production_metrics(record)
    matched, max_error, fields = compare_direct_production(output, direct)
    assert matched is True
    assert max_error == 0.0
    assert fields == []


def test_direct_equivalence_detects_numeric_change():
    record = v3_record()
    output = evaluate_frozen_observation(record, record_index=0)
    direct = direct_production_metrics(record)
    direct["odi_trans"] += 1.0e-10
    matched, max_error, fields = compare_direct_production(output, direct)
    assert matched is False
    assert max_error == pytest.approx(1.0e-10)
    assert fields == ["odi_trans"]


def test_direct_equivalence_detects_boolean_change():
    record = v3_record()
    output = evaluate_frozen_observation(record, record_index=0)
    direct = direct_production_metrics(record)
    direct["degeneracy_triggered"] = not direct["degeneracy_triggered"]
    matched, _, fields = compare_direct_production(output, direct)
    assert matched is False
    assert fields == ["degeneracy_triggered"]
