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

__all__ = [
    "ADAPTER_CONTRACT_VERSION",
    "CHECKSUM_ALGORITHM",
    "DETECTOR_COLUMN_MAP",
    "FIRST_VALID_RECORD_VERSION",
    "SCHEMA_VERSION",
    "SKIP_REASONS",
    "validate_first_valid_observation_record",
    "validate_scan_lifecycle_record",
]
