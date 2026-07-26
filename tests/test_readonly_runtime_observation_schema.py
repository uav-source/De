import copy
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from fastlio2_adapter.readonly_observation_schema import (
    validate_first_valid_observation_record,
)
from fastlio2_adapter.readonly_runtime_observation_schema import (
    validate_runtime_observation,
)


ROOT = Path(__file__).resolve().parents[1]


def runtime_record():
    spec = importlib.util.spec_from_file_location(
        "day4_fixture_runtime_schema",
        ROOT / "scripts/42_run_harmful_bias_day4_synthetic_adapter.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    record = copy.deepcopy(module.build_synthetic_observations()["well_conditioned"])
    record.update(
        {
            "schema_version": "readonly_observation_v2",
            "record_version": "readonly_observation_v2",
            "record_source": "FASTLIO2_RUNTIME",
            "synthetic_only": False,
            "run_id": "multihyp_day5_equivalence_v1_ON_R1",
            "sequence_id": "avia_quick_shack",
            "fastlio2_commit": "a" * 40,
            "fastlio2_binary_sha256": "b" * 64,
            "bag_sha256": "c" * 64,
            "config_bundle_sha256": "d" * 64,
            "adapter_contract_version": "fastlio2-readonly-observation-v2",
        }
    )
    return record


def test_runtime_v2_record_passes_python_and_json_schema():
    record = runtime_record()
    validate_runtime_observation(record)
    schema = json.loads(
        (ROOT / "schemas/harmful_bias/readonly_observation_v2.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(record)


def test_v1_and_v2_cannot_be_confused():
    record = runtime_record()
    with pytest.raises(ValueError):
        validate_first_valid_observation_record(record)
    v1 = copy.deepcopy(record)
    for field in (
        "record_source",
        "run_id",
        "sequence_id",
        "fastlio2_commit",
        "fastlio2_binary_sha256",
        "bag_sha256",
        "config_bundle_sha256",
        "adapter_contract_version",
    ):
        v1.pop(field)
    v1.update(
        schema_version="fastlio2-readonly-observation-v1",
        record_version="readonly_observation_v1",
        synthetic_only=True,
    )
    with pytest.raises(ValueError):
        validate_runtime_observation(v1)


@pytest.mark.parametrize(
    "field",
    [
        "pose_gt",
        "future_frame",
        "holdout_label",
        "candidate_offsets",
        "candidate_costs",
        "imu_conflict",
        "harmful_trigger",
    ],
)
def test_runtime_schema_rejects_deferred_or_oracle_fields(field):
    record = runtime_record()
    record[field] = 1
    with pytest.raises(ValueError, match="forbidden"):
        validate_runtime_observation(record)


def test_runtime_validation_does_not_mutate_input():
    record = runtime_record()
    before = copy.deepcopy(record)
    validate_runtime_observation(record)
    assert record == before
