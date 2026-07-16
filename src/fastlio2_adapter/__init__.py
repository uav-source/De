"""Read-only FAST-LIO2 adapter contracts."""

from .readonly_observation_schema import (
    ADAPTER_CONTRACT_VERSION,
    CHECKSUM_ALGORITHM,
    DETECTOR_COLUMN_MAP,
    FIRST_VALID_RECORD_VERSION,
    SCHEMA_VERSION,
    SKIP_REASONS,
    validate_first_valid_observation_record,
    validate_scan_lifecycle_record,
)
from .detector_adapter import (
    DETECTOR_RESIDUAL_INPUT_FIELD,
    DETECTOR_STATE_ORDER,
    DETECTOR_TRANSLATION_FRAME,
    PRIOR_COVARIANCE_USED_BY_DETECTOR,
    evaluate_readonly_observation,
    load_production_detector_contract,
    prepare_production_detector_input,
)
from .detector_output_schema import (
    INVALID_REASONS,
    PRIMARY_WEAK_DIRECTION_FRAME,
    canonical_sha256,
    validate_readonly_detector_output,
)

__all__ = [
    "ADAPTER_CONTRACT_VERSION",
    "CHECKSUM_ALGORITHM",
    "DETECTOR_COLUMN_MAP",
    "FIRST_VALID_RECORD_VERSION",
    "SCHEMA_VERSION",
    "SKIP_REASONS",
    "validate_first_valid_observation_record",
    "validate_scan_lifecycle_record",
    "DETECTOR_RESIDUAL_INPUT_FIELD",
    "DETECTOR_STATE_ORDER",
    "DETECTOR_TRANSLATION_FRAME",
    "PRIOR_COVARIANCE_USED_BY_DETECTOR",
    "evaluate_readonly_observation",
    "load_production_detector_contract",
    "prepare_production_detector_input",
    "INVALID_REASONS",
    "PRIMARY_WEAK_DIRECTION_FRAME",
    "canonical_sha256",
    "validate_readonly_detector_output",
]
