from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType

import pytest

from phase_a_harness.formal_runtime_state_machine import FormalRuntimeState
from phase_a_harness.qualification_json_native import (
    assert_strict_json_native_tree,
    scan_non_json_native_leaves,
    to_strict_json_native,
)
from phase_a_harness.runtime_lifecycle_io import (
    atomic_create_canonical_json,
    read_canonical_json,
)


REPOSITORY = Path(__file__).resolve().parents[1]
QUALIFIER = (
    REPOSITORY
    / "scripts/qualify_synthetic_confirmatory_v3_bootstrap_repair_r3.py"
)


def _load_qualifier() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "qualification_final_aggregate_under_test", QUALIFIER
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _complete_representative(module: ModuleType) -> dict[str, object]:
    absent = {
        "state": FormalRuntimeState.ABSENT,
        "reasons": ["runtime root is absent"],
    }
    bootstrap_only = {
        "state": FormalRuntimeState.BOOTSTRAP_ONLY,
        "reasons": ["command log is bound and immutable lock is absent"],
    }
    resumable = {
        "state": FormalRuntimeState.RESUMABLE,
        "reasons": ["command log and immutable lock are valid"],
    }
    bootstrap = {
        "created": True,
        "state_before": FormalRuntimeState.ABSENT,
        "state_after": FormalRuntimeState.BOOTSTRAP_ONLY,
    }
    lock_transition = {
        "created": True,
        "state_before": FormalRuntimeState.BOOTSTRAP_ONLY,
        "state_after": FormalRuntimeState.RESUMABLE,
    }
    git_gate_reports = [
        {
            "RUNTIME_GIT_GATE_PASS": True,
            "checkpoint": checkpoint,
            "tracked_diff_count": 0,
            "index_diff_count": 0,
            "untracked_file_count": 0,
        }
        for checkpoint in module.REQUIRED_GIT_CHECKPOINTS
    ]
    return module._representative_final_aggregate(
        absent=absent,
        bootstrap_only=bootstrap_only,
        resumable=resumable,
        bootstrap=bootstrap,
        lock_transition=lock_transition,
        formal_runtime_state=FormalRuntimeState.RESUMABLE,
        git_gate_reports=git_gate_reports,
    )


def test_production_builder_rejects_missing_and_extra_top_level_fields() -> None:
    module = _load_qualifier()
    complete = _complete_representative(module)

    missing = dict(complete)
    missing.pop("states")
    with pytest.raises(ValueError, match="missing=.*states"):
        module.build_qualification_final_aggregate(missing)

    extra = {**complete, "unreviewed_field": None}
    with pytest.raises(ValueError, match="extra=.*unreviewed_field"):
        module.build_qualification_final_aggregate(extra)

    with pytest.raises(TypeError, match="exact dict"):
        module.build_qualification_final_aggregate(list(complete.items()))


def test_complete_production_shape_has_exact_eleven_inventory_leaves() -> None:
    module = _load_qualifier()
    aggregate = _complete_representative(module)
    inventory = scan_non_json_native_leaves(aggregate)

    assert len(aggregate) == len(module.FINAL_AGGREGATE_EXACT_FIELDS) == 103
    assert set(aggregate) == set(module.FINAL_AGGREGATE_EXACT_FIELDS)
    assert len(inventory) == 11
    assert {row["json_path"] for row in inventory} == set(
        module.EXPECTED_FORMAL_RUNTIME_STATE_PATHS
    )
    assert {row["class_name"] for row in inventory} == {"FormalRuntimeState"}
    assert all(row["scientific_field"] is False for row in inventory)


def test_complete_production_shape_roundtrips_through_frozen_writer(
    tmp_path: Path,
) -> None:
    module = _load_qualifier()
    aggregate = _complete_representative(module)
    output = tmp_path / "qualification_final_aggregate.json"

    normalized, inventory, audit, report = module._strict_roundtrip(
        aggregate=aggregate,
        output=output,
        atomic_writer=atomic_create_canonical_json,
        scan_non_json_native_leaves=scan_non_json_native_leaves,
        to_strict_json_native=to_strict_json_native,
        assert_strict_json_native_tree=assert_strict_json_native_tree,
    )

    assert read_canonical_json(output) == normalized
    assert len(inventory) == len(audit) == 11
    assert scan_non_json_native_leaves(normalized) == []
    assert report["FINAL_AGGREGATE_JSON_NATIVE_PASS"] is True
    assert report["FINAL_AGGREGATE_ATOMIC_WRITE_PASS"] is True
    assert report["FINAL_AGGREGATE_RELOAD_EQUALITY_PASS"] is True
    assert report["NON_JSON_NATIVE_LEAF_COUNT_AFTER"] == 0
    assert report["UNKNOWN_TYPE_COERCION_COUNT"] == 0
    assert report["NONFINITE_JSON_NUMBER_COUNT"] == 0


def test_full_aggregate_normalization_does_not_mutate_input() -> None:
    module = _load_qualifier()
    aggregate = _complete_representative(module)
    before = scan_non_json_native_leaves(aggregate)

    normalized = to_strict_json_native(aggregate)

    assert scan_non_json_native_leaves(aggregate) == before
    assert normalized is not aggregate
    assert normalized["states"] is not aggregate["states"]
    assert aggregate["states"]["absent"]["state"] is FormalRuntimeState.ABSENT


def test_roundtrip_rejects_native_field_mutation_by_normalizer(
    tmp_path: Path,
) -> None:
    module = _load_qualifier()
    aggregate = _complete_representative(module)

    def mutating_normalizer(
        value: dict[str, object],
        path: str = "$",
        *,
        conversion_audit: list[dict[str, object]] | None = None,
    ) -> object:
        value["schema_version"] = "silently-mutated"
        return to_strict_json_native(
            value, path=path, conversion_audit=conversion_audit
        )

    with pytest.raises(RuntimeError, match="mutated its input object"):
        module._strict_roundtrip(
            aggregate=aggregate,
            output=tmp_path / "must-not-exist.json",
            atomic_writer=atomic_create_canonical_json,
            scan_non_json_native_leaves=scan_non_json_native_leaves,
            to_strict_json_native=mutating_normalizer,
            assert_strict_json_native_tree=assert_strict_json_native_tree,
        )

    assert not (tmp_path / "must-not-exist.json").exists()


def test_qualifier_has_one_builder_and_no_automatic_json_coercion() -> None:
    module = _load_qualifier()
    source = inspect.getsource(module)

    assert source.count("def build_qualification_final_aggregate(") == 1
    assert source.count("result = build_qualification_final_aggregate({") == 1
    assert "default=str" not in source
    assert "default = str" not in source
    assert "json.dumps(default=" not in source
    assert 'fresh.get("pairing_mismatch_count") == 0' in source
    assert 'fresh.get("outcome_mismatch_count") == 0' in source
    assert 'resumed.get("pairing_mismatch_count") == 0' in source
    assert 'resumed.get("outcome_mismatch_count") == 0' in source
