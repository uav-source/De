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
from .in_call_immutability import (
    SCHEMA_VERSION as IN_CALL_IMMUTABILITY_SCHEMA_VERSION,
    evaluate_gate as evaluate_in_call_immutability_gate,
    validate_status as validate_in_call_immutability_status,
)
from .frozen_observation import (
    evaluate_freeze_gate,
    evaluate_remediation_gate,
    validate_core_observation_integrity,
    validate_freeze_manifest,
)
from .experiment_a_stage_hash import (
    HASH_ALGORITHM as EXPERIMENT_A_HASH_ALGORITHM,
    MAP_DIGEST_VERSION as EXPERIMENT_A_MAP_DIGEST_VERSION,
    validate_status as validate_experiment_a_stage_hash_status,
)
from .experiment_a_stage_classifier import (
    compare_pair as compare_experiment_a_stage_hash_pair,
)
from .day7_map_point_identity import (
    POINT_IDENTITY_ALGORITHM as DAY7_POINT_IDENTITY_ALGORITHM,
    point_identity as day7_point_identity,
)
from .day7_map_update_root_cause import (
    compare_run_pair as compare_day7_map_update_pair,
)
from .day8_range_query import (
    validate_run_query_trace as validate_day8_range_query_trace,
)
from .day8_query_root_cause import (
    classify_query_difference as classify_day8_query_difference,
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
    "IN_CALL_IMMUTABILITY_SCHEMA_VERSION",
    "evaluate_in_call_immutability_gate",
    "validate_in_call_immutability_status",
    "evaluate_freeze_gate",
    "evaluate_remediation_gate",
    "validate_core_observation_integrity",
    "validate_freeze_manifest",
    "EXPERIMENT_A_HASH_ALGORITHM",
    "EXPERIMENT_A_MAP_DIGEST_VERSION",
    "validate_experiment_a_stage_hash_status",
    "compare_experiment_a_stage_hash_pair",
    "DAY7_POINT_IDENTITY_ALGORITHM",
    "day7_point_identity",
    "compare_day7_map_update_pair",
    "validate_day8_range_query_trace",
    "classify_day8_query_difference",
]
