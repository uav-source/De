"""Schemas and round-trip validation for the Stage 2 Day 11A case lock."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Mapping, Sequence

from eval.stage2_failure_deterministic_case import (
    CANDIDATE_POOL_SCHEMA_VERSION,
    DAY11B_REPLAY_STRESS_REGIMES,
    HISTORICAL_TEST_EXECUTED_STRESS_REGIMES,
    LEGACY_STAGE2B_STRESS_NAME,
    REQUIRED_METHODS,
    SELECTION_ALGORITHM_VERSION,
    STAGE2C_ALLOWED_STRESS_REGIMES,
    canonical_candidate_string,
    deterministic_case_index,
    selected_case_record,
)


DAY11A_CONFIG_SCHEMA_VERSION = "stage2_failure_day11a_case_lock_v1"
DAY11A_PROTOCOL_SCHEMA_VERSION = "stage2_failure_day11a_protocol_revision_v1"
DAY11A_RUN_SCHEMA_VERSION = "stage2_failure_day11a_run_manifest_v1"
CANDIDATE_POOL_FIELDS = (
    "schema_version",
    "sweep",
    "candidate_index",
    "level",
    "geometry_seed",
    "sensor_seed",
    "process_seed",
    "canonical_candidate_string",
    "candidate_sha256",
    "selected",
)


def validate_candidate_pool_rows(
    rows: Sequence[Mapping[str, Any]],
    geometry_candidate_count: int,
    observation_candidate_count: int,
) -> Mapping[str, int]:
    """Validate exact fields, canonical order, hashes, uniqueness, and selection."""

    expected_total = int(geometry_candidate_count) + int(observation_candidate_count)
    if len(rows) != expected_total:
        raise ValueError("candidate pool row count is inconsistent")
    expected_sweeps = (
        ["geometry"] * int(geometry_candidate_count)
        + ["observation"] * int(observation_candidate_count)
    )
    actual_sweeps = [str(row.get("sweep")) for row in rows]
    if actual_sweeps != expected_sweeps:
        raise ValueError("candidate pool sweep order is not canonical")

    duplicate_count = 0
    seen = set()
    selected_counts = {"geometry": 0, "observation": 0}
    for sweep, count in (
        ("geometry", int(geometry_candidate_count)),
        ("observation", int(observation_candidate_count)),
    ):
        sweep_rows = [row for row in rows if str(row.get("sweep")) == sweep]
        indices = [int(row.get("candidate_index", -1)) for row in sweep_rows]
        if indices != list(range(count)):
            raise ValueError(f"{sweep} candidate indices are not contiguous")
        tuples = [
            (
                str(row.get("level")),
                int(row.get("geometry_seed")),
                int(row.get("sensor_seed")),
                int(row.get("process_seed")),
            )
            for row in sweep_rows
        ]
        if tuples != sorted(tuples):
            raise ValueError(f"{sweep} candidate tuple order is not canonical")

    for row in rows:
        if set(row) != set(CANDIDATE_POOL_FIELDS):
            raise ValueError("candidate pool schema fields differ from the contract")
        if row.get("schema_version") != CANDIDATE_POOL_SCHEMA_VERSION:
            raise ValueError("candidate pool schema version differs from the contract")
        key = (
            str(row["sweep"]),
            str(row["level"]),
            int(row["geometry_seed"]),
            int(row["sensor_seed"]),
            int(row["process_seed"]),
        )
        duplicate_count += int(key in seen)
        seen.add(key)
        canonical = canonical_candidate_string(*key[1:])
        if str(row["canonical_candidate_string"]) != canonical:
            raise ValueError("candidate canonical string mismatch")
        expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if str(row["candidate_sha256"]) != expected_hash:
            raise ValueError("candidate SHA-256 mismatch")
        selected = _boolean(row["selected"])
        selected_counts[str(row["sweep"])] += int(selected)
    if duplicate_count:
        raise ValueError("candidate pool contains duplicate primary keys")
    if selected_counts != {"geometry": 1, "observation": 1}:
        raise ValueError("each sweep must contain exactly one selected candidate")
    return {
        "candidate_duplicate_count": duplicate_count,
        "geometry_selected_row_count": selected_counts["geometry"],
        "observation_selected_row_count": selected_counts["observation"],
    }


def validate_case_lock(
    lock: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    candidate_pool_sha256: str,
    config: Mapping[str, Any],
) -> None:
    """Reject any scientific or provenance mutation of a Day 11A lock."""

    required_fields = {
        "schema_version",
        "lock_type",
        "selection_algorithm_version",
        "created_at",
        "protocol_revision_reason",
        "history_recovery_pass",
        "history_trial_tables_available",
        "historical_representativeness_claim_allowed",
        "stage2c_tag",
        "stage2c_commit",
        "stage2c_test_manifest_path",
        "stage2c_test_manifest_sha256",
        "stage2c_update_lock_path",
        "stage2c_update_lock_sha256",
        "stage2c_common_config_path",
        "stage2c_common_config_sha256",
        "stage2c_test_config_path",
        "stage2c_test_config_sha256",
        "stage2c_stress_config_path",
        "stage2c_stress_config_sha256",
        "seed_source_consistency_pass",
        "stress_source_validation_pass",
        "test_geometry_seeds",
        "test_sensor_seeds",
        "test_process_seeds",
        "stage2c_allowed_stress_regimes",
        "historical_test_executed_stress_regimes",
        "day11b_replay_stress_regimes",
        "gross_outlier_control_replayed",
        "stress_name_alias_used",
        "legacy_stage2b_stress_name_used",
        "geometry_candidate_levels",
        "geometry_candidate_count",
        "geometry_hash_label",
        "geometry_hash_digest_hex",
        "geometry_hash_integer_decimal",
        "geometry_selected_index",
        "geometry_selected_case",
        "observation_candidate_levels",
        "observation_candidate_count",
        "observation_hash_label",
        "observation_hash_digest_hex",
        "observation_hash_integer_decimal",
        "observation_selected_index",
        "observation_selected_case",
        "required_methods",
        "required_stress_regimes",
        "required_replay_stress_regimes",
        "expected_day11b_method_replay_count",
        "candidate_pool_path",
        "candidate_pool_sha256",
        "selection_used_metrics",
        "selection_used_innovation",
        "selection_used_cusum",
        "selection_used_gt_error",
        "selection_used_plot_visibility",
        "selection_used_manual_override",
        "selection_used_random_sampling",
        "replay_performed",
        "figures_generated",
        "threshold_created",
        "auroc_computed",
        "fpr_computed",
        "f1_computed",
        "fast_lio2_integrated",
        "git_branch",
        "git_commit_at_lock",
        "git_status_clean_at_lock",
        "source_tree_sha256",
        "day11a_config_sha256",
    }
    missing = sorted(required_fields - set(lock))
    if missing:
        raise ValueError(f"case lock is missing fields: {missing}")
    expected_scalars = {
        "schema_version": DAY11A_CONFIG_SCHEMA_VERSION,
        "lock_type": "preregistered_deterministic_diagnostic_cases",
        "selection_algorithm_version": SELECTION_ALGORITHM_VERSION,
        "history_recovery_pass": False,
        "history_trial_tables_available": False,
        "historical_representativeness_claim_allowed": False,
        "stage2c_tag": config["stage2c_tag"],
        "stage2c_commit": config["expected_stage2c_commit"],
        "seed_source_consistency_pass": True,
        "stress_source_validation_pass": True,
        "gross_outlier_control_replayed": False,
        "stress_name_alias_used": False,
        "legacy_stage2b_stress_name_used": False,
        "expected_day11b_method_replay_count": 8,
        "candidate_pool_path": "candidate_pool.csv",
        "candidate_pool_sha256": str(candidate_pool_sha256),
        "selection_used_metrics": False,
        "selection_used_innovation": False,
        "selection_used_cusum": False,
        "selection_used_gt_error": False,
        "selection_used_plot_visibility": False,
        "selection_used_manual_override": False,
        "selection_used_random_sampling": False,
        "replay_performed": False,
        "figures_generated": False,
        "threshold_created": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "f1_computed": False,
        "fast_lio2_integrated": False,
        "git_status_clean_at_lock": True,
    }
    for field, expected in expected_scalars.items():
        if lock.get(field) != expected or type(lock.get(field)) is not type(expected):
            raise ValueError(f"case lock field {field} differs from the contract")
    expected_lists = {
        "required_methods": list(REQUIRED_METHODS),
        "required_stress_regimes": list(DAY11B_REPLAY_STRESS_REGIMES),
        "required_replay_stress_regimes": list(DAY11B_REPLAY_STRESS_REGIMES),
        "stage2c_allowed_stress_regimes": list(STAGE2C_ALLOWED_STRESS_REGIMES),
        "historical_test_executed_stress_regimes": list(
            HISTORICAL_TEST_EXECUTED_STRESS_REGIMES
        ),
        "day11b_replay_stress_regimes": list(DAY11B_REPLAY_STRESS_REGIMES),
        "geometry_candidate_levels": list(config["geometry_candidate_levels"]),
        "observation_candidate_levels": list(config["observation_candidate_levels"]),
    }
    for field, expected in expected_lists.items():
        if list(lock.get(field, [])) != expected:
            raise ValueError(f"case lock field {field} differs from the contract")
        if LEGACY_STAGE2B_STRESS_NAME in list(lock.get(field, [])):
            raise ValueError("legacy Stage 2B stress name is forbidden")
    replay_count = (
        2
        * len(lock["day11b_replay_stress_regimes"])
        * len(lock["required_methods"])
    )
    if replay_count != int(lock["expected_day11b_method_replay_count"]):
        raise ValueError("Day 11B replay matrix count differs from the contract")

    counts = {
        "geometry": int(lock["geometry_candidate_count"]),
        "observation": int(lock["observation_candidate_count"]),
    }
    validate_candidate_pool_rows(rows, counts["geometry"], counts["observation"])
    for sweep in ("geometry", "observation"):
        label = str(lock[f"{sweep}_hash_label"])
        expected_label = str(config[f"{sweep}_hash_label"])
        if label != expected_label:
            raise ValueError(f"{sweep} hash label differs from the contract")
        digest, selected_index = deterministic_case_index(label, counts[sweep])
        digest_integer = int.from_bytes(bytes.fromhex(digest), "big", signed=False)
        if lock[f"{sweep}_hash_digest_hex"] != digest:
            raise ValueError(f"{sweep} digest differs from the contract")
        if str(lock[f"{sweep}_hash_integer_decimal"]) != str(digest_integer):
            raise ValueError(f"{sweep} digest integer differs from the contract")
        if int(lock[f"{sweep}_selected_index"]) != selected_index:
            raise ValueError(f"{sweep} selected index differs from the contract")
        selected_rows = [
            row
            for row in rows
            if str(row["sweep"]) == sweep and _boolean(row["selected"])
        ]
        if len(selected_rows) != 1:
            raise ValueError(f"{sweep} selected row count differs from the contract")
        if dict(lock[f"{sweep}_selected_case"]) != selected_case_record(
            selected_rows[0]
        ):
            raise ValueError(f"{sweep} selected case differs from candidate pool")
    for field in (
        "stage2c_test_manifest_sha256",
        "stage2c_update_lock_sha256",
        "stage2c_common_config_sha256",
        "stage2c_test_config_sha256",
        "stage2c_stress_config_sha256",
        "source_tree_sha256",
        "day11a_config_sha256",
    ):
        value = str(lock.get(field, ""))
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError(f"case lock field {field} is not a SHA-256")


def validate_protocol_revision_manifest(value: Mapping[str, Any]) -> None:
    """Validate the fixed protocol revision and its conservative claims."""

    expected = {
        "schema_version": DAY11A_PROTOCOL_SCHEMA_VERSION,
        "revision_id": "stage2_day11r1_missing_trial_provenance",
        "previous_protocol": "historical representative seed replay",
        "revised_protocol": "preregistered deterministic diagnostic case replay",
        "recovery_audit_performed": True,
        "recovery_audit_pass": False,
        "historical_test_completed_claim": True,
        "historical_trial_level_results_available": False,
        "historical_aggregate_results_available": True,
        "trial_level_results_reconstructed": False,
        "trial_level_results_inferred": False,
        "representative_seed_claim_retained": False,
        "day11_case_claim": "mechanism-oriented deterministic diagnostic cases only",
        "day12_figure_claim": "diagnostic visualization only, not representative statistics",
        "day13_role": "primary new-seed multi-case statistical diagnosis",
        "STAGE2C_HISTORY_RECOVERY_PASS": False,
        "DAY11_REPLAY_PASS": False,
        "DAY12_DIAGNOSTIC_FIGURES_AUTHORIZED": False,
    }
    for field, expected_value in expected.items():
        if value.get(field) != expected_value or type(value.get(field)) is not type(
            expected_value
        ):
            raise ValueError(f"protocol revision field {field} differs from contract")
    missing_files = list(value.get("missing_files", []))
    if len(missing_files) != 3:
        raise ValueError("protocol revision must record all three missing sources")


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"expected a strict boolean, received {value!r}")
