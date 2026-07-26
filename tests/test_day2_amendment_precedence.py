from pathlib import Path

import pytest

from capture_range.day2_protocol import (
    AMENDMENT_ROOT_SECTIONS,
    PROTOCOL_AMENDMENT_MANIFEST_FIELDS,
    load_effective_day2_protocol,
)


ROOT = Path(__file__).resolve().parents[1]


def test_effective_protocol_preserves_base_and_amendment_as_separate_layers():
    effective = load_effective_day2_protocol(ROOT)

    assert effective.base["protocol"]["version"] == "1.0.0"
    assert effective.amendment["amendment"]["version"] == "1.1.0"
    assert tuple(effective.amendment) == AMENDMENT_ROOT_SECTIONS
    assert effective.amendment["amendment"]["amendment_precedence"] == {
        "rule": "this_amendment_supersedes_only_the_explicitly_listed_v1_0_clauses",
        "unlisted_v1_0_clauses_remain_frozen": True,
        "original_v1_0_files_must_not_be_modified": True,
    }
    assert effective.resolution("scene_generation_semantics") is (
        effective.amendment["scene_generation_semantics"]
    )
    with pytest.raises(KeyError):
        effective.resolution("unlisted_in_amendment")


def test_unlisted_v1_0_scientific_values_remain_unchanged():
    effective = load_effective_day2_protocol(ROOT)
    inheritance = effective.base["inheritance"]

    assert inheritance["translation_success_threshold_m"] == 0.02
    assert inheritance["rotation_success_threshold_deg"] == 0.5
    assert effective.base["amplitudes"]["translation_m"] == (
        0.0, 0.01, 0.02, 0.05, 0.10, 0.20, 0.40, 0.80,
    )
    assert effective.base["amplitudes"]["rotation_deg"] == (
        0.0, 0.25, 0.50, 1.0, 2.0, 5.0, 10.0, 20.0,
    )
    assert effective.base["splits"]["development"]["geometry_seeds"] == (
        1101, 1103, 1107,
    )
    assert effective.base["splits"]["test"]["geometry_seeds"] == (
        1201, 1213, 1223,
    )


def test_required_amendment_manifest_provenance_is_exact_and_read_only():
    effective = load_effective_day2_protocol(ROOT)

    assert dict(effective.manifest_fields) == {
        "protocol_amendment_reason": "v1_0_was_not_uniquely_executable",
        "protocol_amendment_timing": "before_any_day2_development_or_test_run",
        "seed_consumed_before_amendment": False,
    }
    assert effective.manifest_fields is PROTOCOL_AMENDMENT_MANIFEST_FIELDS
    with pytest.raises(TypeError):
        effective.manifest_fields["seed_consumed_before_amendment"] = True
    with pytest.raises(TypeError):
        effective.base["protocol"]["version"] = "changed"
