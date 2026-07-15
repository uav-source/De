"""Frozen eight-row replay matrix for Stage 2 Day 11B."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence


REPLAY_PLAN_SCHEMA_VERSION = "stage2_failure_day11b_replay_plan_v1"
REPLAY_METHODS = ("huber_full", "huber_projected_gain")
REPLAY_STRESSES = ("clean", "coherent_subhuber_slip")
REPLAY_SWEEPS = ("geometry", "observation")
REPLAY_PLAN_FIELDS = (
    "schema_version", "case_id", "sweep", "level", "geometry_seed",
    "sensor_seed", "process_seed", "stress", "method", "case_lock_sha256",
    "stage2c_commit", "stage2c_test_manifest_sha256", "stage2c_update_lock_sha256",
    "stage2c_common_config_sha256", "stage2c_test_config_sha256",
    "stage2c_stress_config_sha256", "expected_full_sequence", "selected_case_claim",
    "independent_test", "representative_seed_claim", "threshold_selection_allowed",
    "stage2_gate_decision_allowed",
)


def build_replay_plan(verification: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """Build the locked sweep/stress/method product in its canonical order."""

    rows = []
    cases = {
        "geometry": verification["selected_geometry_case"],
        "observation": verification["selected_observation_case"],
    }
    for sweep in REPLAY_SWEEPS:
        selected = cases[sweep]
        for stress in REPLAY_STRESSES:
            for method in REPLAY_METHODS:
                case_id = (
                    f"{sweep}_{selected['level']}_g{int(selected['geometry_seed'])}_"
                    f"s{int(selected['sensor_seed'])}_p{int(selected['process_seed'])}_"
                    f"{stress}_{method}"
                )
                rows.append({
                    "schema_version": REPLAY_PLAN_SCHEMA_VERSION,
                    "case_id": case_id,
                    "sweep": sweep,
                    "level": str(selected["level"]),
                    "geometry_seed": int(selected["geometry_seed"]),
                    "sensor_seed": int(selected["sensor_seed"]),
                    "process_seed": int(selected["process_seed"]),
                    "stress": stress,
                    "method": method,
                    "case_lock_sha256": str(verification["day11a_case_lock_sha256"]),
                    "stage2c_commit": str(verification["stage2c_commit"]),
                    "stage2c_test_manifest_sha256": str(verification["stage2c_test_manifest_sha256"]),
                    "stage2c_update_lock_sha256": str(verification["stage2c_update_lock_sha256"]),
                    "stage2c_common_config_sha256": str(verification["stage2c_common_config_sha256"]),
                    "stage2c_test_config_sha256": str(verification["stage2c_test_config_sha256"]),
                    "stage2c_stress_config_sha256": str(verification["stage2c_stress_config_sha256"]),
                    "expected_full_sequence": True,
                    "selected_case_claim": "preregistered deterministic diagnostic case",
                    "independent_test": False,
                    "representative_seed_claim": False,
                    "threshold_selection_allowed": False,
                    "stage2_gate_decision_allowed": False,
                })
    validate_replay_plan(rows, verification)
    return rows


def validate_replay_plan(
    rows: Sequence[Mapping[str, Any]], verification: Mapping[str, Any]
) -> None:
    if len(rows) != 8 or int(verification.get("expected_replay_count", -1)) != 8:
        raise ValueError("Day 11B replay plan must contain exactly eight rows")
    if len({str(row.get("case_id")) for row in rows}) != 8:
        raise ValueError("Day 11B replay case IDs must be unique")
    expected_order = [
        (sweep, stress, method)
        for sweep in REPLAY_SWEEPS
        for stress in REPLAY_STRESSES
        for method in REPLAY_METHODS
    ]
    actual_order = [
        (str(row.get("sweep")), str(row.get("stress")), str(row.get("method")))
        for row in rows
    ]
    if actual_order != expected_order:
        raise ValueError("Day 11B replay matrix order or membership changed")
    for row in rows:
        if set(row) != set(REPLAY_PLAN_FIELDS):
            raise ValueError("Day 11B replay plan schema changed")
        if row["schema_version"] != REPLAY_PLAN_SCHEMA_VERSION:
            raise ValueError("Day 11B replay plan schema version changed")
        method = str(row["method"])
        if method not in REPLAY_METHODS or "oracle" in method.lower():
            raise ValueError("Day 11B replay plan contains a forbidden method")
        if str(row["stress"]) not in REPLAY_STRESSES:
            raise ValueError("Day 11B replay plan contains a forbidden stress")
        expected_claims = {
            "expected_full_sequence": True,
            "selected_case_claim": "preregistered deterministic diagnostic case",
            "independent_test": False,
            "representative_seed_claim": False,
            "threshold_selection_allowed": False,
            "stage2_gate_decision_allowed": False,
        }
        if any(row.get(field) != value for field, value in expected_claims.items()):
            raise ValueError("Day 11B replay plan contains an unsafe claim")
        if str(row["case_lock_sha256"]) != str(verification["day11a_case_lock_sha256"]):
            raise ValueError("Day 11B replay plan case-lock hash changed")


def replay_plan_document(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return {
        "schema_version": REPLAY_PLAN_SCHEMA_VERSION,
        "expected_replay_count": 8,
        "method_list": list(REPLAY_METHODS),
        "replay_stress_list": list(REPLAY_STRESSES),
        "rows": [dict(row) for row in rows],
    }
