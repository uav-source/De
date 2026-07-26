from copy import deepcopy

import pytest

from fastlio2_adapter.frozen_observation import (
    FrozenObservationError,
    REQUIRED_GATE_FIELDS,
    validate_freeze_manifest,
)


def valid_manifest():
    value = {
        "schema_version": "frozen_real_observation_manifest_v1",
        "artifact_name": "Degen-LIO Frozen Real Observation Quick Shack v1",
        "artifact_version": "v1",
        "run_id": "multihyp_fallback_frozen_observation_v1",
        "sequence_id": "avia_quick_shack",
        "scientific_label_status": "UNVERIFIED",
        "eligible_as_ground_truth_label": False,
        "eligible_for_auroc_label": False,
        "holdout_or_test": False,
        "redistribution_authorized": False,
        "observation_record_count": 3,
        "binary_sha256": "a" * 64,
        "record_index_sha256": "b" * 64,
        "FROZEN_REAL_OBSERVATION_RECORD_PASS": True,
        "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED": True,
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
    }
    value.update({name: True for name in REQUIRED_GATE_FIELDS})
    return value


def test_manifest_required_fields_pass():
    validate_freeze_manifest(valid_manifest())


def test_scientific_label_must_be_unverified():
    value = valid_manifest()
    value["scientific_label_status"] = "VERIFIED"
    with pytest.raises(FrozenObservationError):
        validate_freeze_manifest(value)


@pytest.mark.parametrize(
    "field",
    (
        "eligible_as_ground_truth_label",
        "eligible_for_auroc_label",
        "holdout_or_test",
        "redistribution_authorized",
    ),
)
def test_scientific_eligibility_fields_stay_false(field):
    value = deepcopy(valid_manifest())
    value[field] = True
    with pytest.raises(FrozenObservationError):
        validate_freeze_manifest(value)


def test_day6_stays_false():
    value = valid_manifest()
    value["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] = True
    with pytest.raises(FrozenObservationError):
        validate_freeze_manifest(value)


def test_offline_remediation_must_preserve_core_binary():
    value = valid_manifest()
    value.update(
        {
            "artifact_version": "1.1",
            "remediation_type": "OFFLINE_ARCHIVE_PROTOCOL_FIX",
            "core_observation_binary_unchanged": False,
        }
    )
    with pytest.raises(FrozenObservationError):
        validate_freeze_manifest(value)
