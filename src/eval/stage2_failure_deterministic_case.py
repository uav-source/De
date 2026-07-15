"""Result-independent deterministic case selection for Stage 2 Day 11A."""

from __future__ import annotations

import hashlib
from itertools import product
from typing import Any, Dict, List, Mapping, Sequence, Tuple


CANDIDATE_POOL_SCHEMA_VERSION = "stage2_failure_day11a_candidate_pool_v1"
SELECTION_ALGORITHM_VERSION = "degen_lio_day11r1_sha256_mod_v1"
STAGE2C_ALLOWED_STRESS_REGIMES = (
    "clean",
    "coherent_subhuber_slip",
    "gross_outlier_control",
)
HISTORICAL_TEST_EXECUTED_STRESS_REGIMES = (
    "clean",
    "coherent_subhuber_slip",
)
DAY11B_REPLAY_STRESS_REGIMES = HISTORICAL_TEST_EXECUTED_STRESS_REGIMES
REQUIRED_METHODS = ("huber_full", "huber_projected_gain")
LEGACY_STAGE2B_STRESS_NAME = "axial_correspondence_slip"


def canonical_candidate_string(
    level: str,
    geometry_seed: int,
    sensor_seed: int,
    process_seed: int,
) -> str:
    """Return the frozen, platform-independent candidate representation."""

    return (
        f"level={str(level)}|geometry_seed={int(geometry_seed)}|"
        f"sensor_seed={int(sensor_seed)}|process_seed={int(process_seed)}"
    )


def deterministic_case_index(label: str, candidate_count: int) -> Tuple[str, int]:
    """Select a zero-based index using the full unsigned big-endian SHA-256."""

    if isinstance(candidate_count, bool) or int(candidate_count) <= 0:
        raise ValueError("candidate_count must be greater than zero")
    digest_bytes = hashlib.sha256(str(label).encode("utf-8")).digest()
    digest_hex = digest_bytes.hex()
    digest_integer = int.from_bytes(digest_bytes, byteorder="big", signed=False)
    return digest_hex, digest_integer % int(candidate_count)


def build_candidate_pool(
    sweep: str,
    levels: Sequence[str],
    geometry_seeds: Sequence[int],
    sensor_seeds: Sequence[int],
    process_seeds: Sequence[int],
) -> List[Dict[str, Any]]:
    """Build the sorted Cartesian pool without reading any outcome data."""

    normalized_sweep = str(sweep)
    if normalized_sweep not in {"geometry", "observation"}:
        raise ValueError("sweep must be geometry or observation")
    normalized_levels = _unique_sorted_strings(levels, "levels")
    normalized_geometry = _unique_sorted_integers(geometry_seeds, "geometry_seeds")
    normalized_sensor = _unique_sorted_integers(sensor_seeds, "sensor_seeds")
    normalized_process = _unique_sorted_integers(process_seeds, "process_seeds")
    if not all(
        (normalized_levels, normalized_geometry, normalized_sensor, normalized_process)
    ):
        raise ValueError("candidate pool dimensions must be non-empty")

    rows: List[Dict[str, Any]] = []
    tuples = sorted(
        product(
            normalized_levels,
            normalized_geometry,
            normalized_sensor,
            normalized_process,
        ),
        key=lambda value: (str(value[0]), int(value[1]), int(value[2]), int(value[3])),
    )
    for candidate_index, (level, geometry_seed, sensor_seed, process_seed) in enumerate(
        tuples
    ):
        canonical = canonical_candidate_string(
            level,
            geometry_seed,
            sensor_seed,
            process_seed,
        )
        rows.append(
            {
                "schema_version": CANDIDATE_POOL_SCHEMA_VERSION,
                "sweep": normalized_sweep,
                "candidate_index": candidate_index,
                "level": level,
                "geometry_seed": geometry_seed,
                "sensor_seed": sensor_seed,
                "process_seed": process_seed,
                "canonical_candidate_string": canonical,
                "candidate_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "selected": False,
            }
        )
    return rows


def select_case(
    candidates: Sequence[Mapping[str, Any]],
    label: str,
) -> Tuple[str, int, List[Dict[str, Any]]]:
    """Return digest, selected index, and a copied pool with one selected row."""

    digest_hex, selected_index = deterministic_case_index(label, len(candidates))
    output = [dict(row) for row in candidates]
    for row in output:
        row["selected"] = int(row["candidate_index"]) == selected_index
    return digest_hex, selected_index, output


def selected_case_record(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract the immutable scientific case key stored in the lock."""

    return {
        "level": str(row["level"]),
        "geometry_seed": int(row["geometry_seed"]),
        "sensor_seed": int(row["sensor_seed"]),
        "process_seed": int(row["process_seed"]),
        "canonical_candidate_string": str(row["canonical_candidate_string"]),
        "candidate_sha256": str(row["candidate_sha256"]),
    }


def validate_stage2c_source_consistency(
    test_config: Mapping[str, Any],
    test_manifest: Mapping[str, Any],
    update_lock: Mapping[str, Any],
    stress_config: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Cross-check the frozen config, compact manifest, and update lock.

    The compact Test manifest does not inline the seed or executed-stress lists.
    It binds them through the matching config bundle and its successful lock
    verification.  The concrete lists are therefore read from the frozen Test
    config and checked exactly against the update lock.
    """

    config_geometry = _integer_list(test_config.get("geometry_seeds"), "geometry_seeds")
    config_sensor = _integer_list(test_config.get("sensor_seeds"), "sensor_seeds")
    config_process = _integer_list(test_config.get("process_seeds"), "process_seeds")
    lock_geometry = _integer_list(
        update_lock.get("reserved_test_geometry_seeds"),
        "reserved_test_geometry_seeds",
    )
    lock_sensor = _integer_list(
        update_lock.get("reserved_test_sensor_seeds"),
        "reserved_test_sensor_seeds",
    )
    lock_process = _integer_list(
        update_lock.get("reserved_test_process_seeds"),
        "reserved_test_process_seeds",
    )
    seed_match = (
        config_geometry == lock_geometry
        and config_sensor == lock_sensor
        and config_process == lock_process
    )
    if not seed_match:
        raise ValueError("Stage 2C Test seed sets differ between config and update lock")

    for development_name, reserved in (
        ("development_geometry_seeds", lock_geometry),
        ("development_sensor_seeds", lock_sensor),
        ("development_process_seeds", lock_process),
    ):
        development = set(_integer_list(update_lock.get(development_name), development_name))
        if development & set(reserved):
            raise ValueError(f"{development_name} overlaps the frozen Test namespace")

    lock_verification = test_manifest.get("lock_verification")
    if not isinstance(lock_verification, Mapping):
        raise ValueError("Stage 2C Test manifest lacks lock verification")
    required_verification = (
        "config_hash_matched",
        "seed_isolation_matched",
        "stress_parameters_matched",
        "source_hash_matched",
    )
    if not all(lock_verification.get(name) is True for name in required_verification):
        raise ValueError("Stage 2C Test manifest did not verify the frozen config/lock")
    if str(test_manifest.get("config_bundle_sha256", "")) != str(
        update_lock.get("config_bundle_sha256", "")
    ):
        raise ValueError("Stage 2C Test manifest and update lock config hashes differ")
    if test_manifest.get("phase") != "test" or test_manifest.get("status") != "OK":
        raise ValueError("Stage 2C Test manifest is not a completed Test run")

    config_allowed = list((stress_config.get("stress_regimes") or {}).keys())
    lock_allowed = list(
        ((update_lock.get("stress_parameters") or {}).get("stress_regimes") or {}).keys()
    )
    executed = list(
        test_manifest.get("executed_stress_regimes", test_config.get("stress_names", []))
    )
    if LEGACY_STAGE2B_STRESS_NAME in config_allowed + lock_allowed + executed:
        raise ValueError("legacy Stage 2B stress name is forbidden in Stage 2C")
    if set(config_allowed) != set(STAGE2C_ALLOWED_STRESS_REGIMES):
        raise ValueError("Stage 2C stress config regime set changed")
    if set(lock_allowed) != set(STAGE2C_ALLOWED_STRESS_REGIMES):
        raise ValueError("Stage 2C update lock regime set changed")
    if set(config_allowed) != set(lock_allowed):
        raise ValueError("Stage 2C stress config and update lock regime sets differ")
    if set(executed) != set(HISTORICAL_TEST_EXECUTED_STRESS_REGIMES):
        raise ValueError("historical Test executed stress regime set changed")
    if not set(executed).issubset(set(lock_allowed)):
        raise ValueError("historical Test stress is absent from the update lock")
    if not set(executed).issubset(set(config_allowed)):
        raise ValueError("historical Test stress is absent from the stress config")

    methods = [str(value) for value in update_lock.get("method_list", [])]
    if not set(REQUIRED_METHODS).issubset(set(methods)):
        raise ValueError("Stage 2C update lock lacks the required Day 11B methods")
    expected_blocks = (
        (1 + 4 + 4)
        * len(config_geometry)
        * len(config_sensor)
        * len(executed)
    )
    expected_trials = expected_blocks * len(config_process) * len(methods)
    for field, expected in (
        ("expected_sensor_stress_blocks", expected_blocks),
        ("sensor_stress_block_count", expected_blocks),
        ("expected_method_trials", expected_trials),
        ("method_trial_count", expected_trials),
    ):
        if int(test_manifest.get(field, -1)) != expected:
            raise ValueError(f"Stage 2C Test manifest {field} is inconsistent")
    if expected_trials != 36000:
        raise ValueError("Stage 2C frozen Test trial declaration is not 36,000")

    return {
        "seed_source_consistency_pass": True,
        "stress_source_validation_pass": True,
        "test_geometry_seeds": config_geometry,
        "test_sensor_seeds": config_sensor,
        "test_process_seeds": config_process,
        "stage2c_allowed_stress_regimes": list(STAGE2C_ALLOWED_STRESS_REGIMES),
        "historical_test_executed_stress_regimes": list(
            HISTORICAL_TEST_EXECUTED_STRESS_REGIMES
        ),
        "manifest_seed_binding_via_frozen_config": True,
        "manifest_stress_binding_via_frozen_config": True,
    }


def _integer_list(value: Any, name: str) -> List[int]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be an explicit integer list")
    output = []
    for item in value:
        if isinstance(item, bool):
            raise ValueError(f"{name} must contain integers")
        output.append(int(item))
    if len(output) != len(set(output)):
        raise ValueError(f"{name} contains duplicates")
    return output


def _unique_sorted_integers(values: Sequence[int], name: str) -> List[int]:
    output = _integer_list(values, name)
    return sorted(output)


def _unique_sorted_strings(values: Sequence[str], name: str) -> List[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a list")
    output = [str(value) for value in values]
    if not output or any(not value for value in output):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(output) != len(set(output)):
        raise ValueError(f"{name} contains duplicates")
    return sorted(output)
