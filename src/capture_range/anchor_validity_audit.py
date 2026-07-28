"""Development-only zero-perturbation anchor validity diagnostics.

This module intentionally reuses the frozen Day 2 Development scene and
registration implementations.  It adds diagnostic measurement conditions and
offline scoring only; it does not alter the capture-range protocol, optimizer,
success thresholds, directions, amplitudes, or confirmatory seed authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import yaml

from .day2_development_protocol import (
    Day2DevelopmentProtocol,
    DevelopmentSeedFirewall,
    canonical_array_sha256,
    canonical_seed,
    canonical_sha256,
    file_sha256,
)
from .day2_development_scene import build_scene_geometry
from .recovery_metrics import (
    evaluate_recovery_success,
    rotation_geodesic_error_rad,
    translation_error_m,
)
from .registration_core import (
    FrozenJacobianBaseline,
    PreparedFullReassociationSession,
    RegistrationEvaluation,
    RegistrationOutcome,
    _solve_robust_step,
    boxplus_pose,
    pose_boxminus,
    prepare_frozen_linearization,
    prepare_full_reassociation_session,
    registration_options,
    run_frozen_jacobian_core,
    run_prepared_full_reassociation_core,
)
from .types import RegistrationSnapshot


ANCHOR_AUDIT_YAML_RELATIVE = Path(
    "configs/capture_range/anchor_validity_audit.yaml"
)

EXPECTED_CONDITIONS = (
    ("NOISE_FREE", 0.0, 0.0, 0.0),
    ("SCAN_NOISE_ONLY", 0.003, 0.0, 0.0),
    ("MAP_NOISE_ONLY", 0.0, 0.001, 0.0),
    ("LOCKED_FULL_NOISE", 0.003, 0.001, 0.01),
)

EXPECTED_CANDIDATES = (
    "GT_REFERENCE_ANCHOR",
    "FULL_ZERO_SOLUTION_ANCHOR",
    "NOISE_FREE_FULL_SOLUTION_ANCHOR",
)

ROOT_CAUSE_VALUES = (
    "REFERENCE_NOT_FIXED_POINT",
    "ZERO_SOLVER_FAILURE",
    "ZERO_ASSOCIATION_SWITCH",
    "NOISE_SHIFT_EXCEEDS_THRESHOLD",
    "DROPOUT_SHIFT_EXCEEDS_THRESHOLD",
    "MULTIPLE_ATTRACTORS",
    "SUCCESS_THRESHOLD_CONFLICT",
    "UNKNOWN",
)


@dataclass(frozen=True)
class AnchorAuditProtocol:
    data: Mapping[str, Any]
    source_sha256: str

    def section(self, name: str) -> Mapping[str, Any]:
        value = self.data.get(str(name))
        if not isinstance(value, Mapping):
            raise KeyError(f"unknown anchor audit section: {name}")
        return value


@dataclass(frozen=True)
class NoiseCondition:
    condition_id: str
    scan_noise_sigma_m: float
    map_noise_sigma_m: float
    scan_dropout_fraction: float
    map_dropout_fraction: float


@dataclass(frozen=True)
class AnchorAuditSnapshotBundle:
    snapshot: RegistrationSnapshot
    scene_id: str
    scene_variant: str
    geometry_seed: int
    measurement_seed: int
    repeat_index: int
    block_id: str
    base_snapshot_id: str
    condition_id: str
    base_snapshot_checksum: str
    scan_checksum: str
    map_checksum: str
    dropout_checksum: str


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(child) for child in value]
    return value


def load_anchor_audit_protocol(root: str | Path) -> AnchorAuditProtocol:
    repository = Path(root).resolve()
    source = repository / ANCHOR_AUDIT_YAML_RELATIVE
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid anchor audit YAML: {source}") from exc
    if type(raw) is not dict:
        raise ValueError("anchor audit YAML root must be a mapping")
    if raw.get("schema_version") != "directional_capture_range_anchor_validity_audit_v1":
        raise ValueError("anchor audit schema version changed")
    authority = raw.get("authority")
    if type(authority) is not dict:
        raise ValueError("anchor audit authority missing")
    expected_authority = {
        "protocol_type": "development_only_diagnostic_audit",
        "scientific_claim_authorized": False,
        "confirmatory_test_authorized": False,
        "confirmatory_test_seed_access": "forbidden",
        "generate_test_lock": False,
        "modify_capture_range_protocol": False,
    }
    for name, expected in expected_authority.items():
        if authority.get(name) != expected:
            raise ValueError(f"anchor audit authority changed: {name}")
    source_lock = raw.get("frozen_source")
    if type(source_lock) is not dict:
        raise ValueError("frozen source declaration missing")
    development_protocol = repository / str(source_lock["development_protocol_path"])
    if file_sha256(development_protocol) != str(source_lock["development_protocol_sha256"]):
        raise ValueError("frozen Development protocol hash changed")
    contract = raw.get("frozen_contract")
    if type(contract) is not dict:
        raise ValueError("frozen contract missing")
    if float(contract.get("translation_success_threshold_m", -1.0)) != 0.02:
        raise ValueError("translation success threshold changed")
    if float(contract.get("rotation_success_threshold_deg", -1.0)) != 0.5:
        raise ValueError("rotation success threshold changed")
    protocol = AnchorAuditProtocol(_freeze(raw), file_sha256(source))
    noise_conditions(protocol)
    if tuple(protocol.section("anchor_candidates")["candidates_in_order"]) != EXPECTED_CANDIDATES:
        raise ValueError("anchor candidate set or order changed")
    return protocol


def noise_conditions(protocol: AnchorAuditProtocol) -> tuple[NoiseCondition, ...]:
    section = protocol.section("noise_ablation")
    rows = tuple(section["conditions_in_order"])
    if len(rows) != 4:
        raise ValueError("anchor audit requires exactly four noise conditions")
    map_dropout = float(section["map_dropout_fraction"])
    result = tuple(
        NoiseCondition(
            str(row["condition_id"]),
            float(row["scan_noise_sigma_m"]),
            float(row["map_noise_sigma_m"]),
            float(row["scan_dropout_fraction"]),
            map_dropout,
        )
        for row in rows
    )
    observed = tuple(
        (
            value.condition_id,
            value.scan_noise_sigma_m,
            value.map_noise_sigma_m,
            value.scan_dropout_fraction,
        )
        for value in result
    )
    if observed != EXPECTED_CONDITIONS or map_dropout != 0.0:
        raise ValueError("predeclared four-condition noise ablation changed")
    return result


def _registration_config(protocol: Day2DevelopmentProtocol) -> dict[str, Any]:
    result = {
        "registration": _plain(protocol.section("registration")),
        "success": _plain(protocol.section("success")),
    }
    for internal in (
        "backend",
        "correspondence_tie_breaking",
        "full_reassociation_rebuilds_each_nonlinear_evaluation",
        "fixed_local_map_kdtree_reuse_within_base_snapshot_allowed",
        "frozen_jacobian_prepared_once_per_base_snapshot",
        "optimizer_inputs_exclude_direction_roles_and_theoretical_weak_direction",
        "execution_matrix",
        "expected_trial_rows",
    ):
        result["registration"].pop(internal, None)
    return result


def assert_optimizer_snapshot_metadata_safe(metadata: Mapping[str, Any]) -> None:
    """Reject GT or offline direction-role fields before optimizer creation."""

    forbidden = (
        "theoretical",
        "weak_direction",
        "direction_role",
        "pose_gt",
        "axis_gt",
    )
    metadata_text = json.dumps(_plain(metadata), sort_keys=True).lower()
    if any(token in metadata_text for token in forbidden):
        raise RuntimeError("GT or direction-role metadata leaked into audit snapshot")


def build_anchor_condition_snapshots(
    development_protocol: Day2DevelopmentProtocol,
    audit_protocol: AnchorAuditProtocol,
    firewall: DevelopmentSeedFirewall,
    scene_variant: str,
    geometry_seed: int,
    measurement_seed: int,
    repeat_index: int,
) -> tuple[AnchorAuditSnapshotBundle, ...]:
    """Realize exactly the four predeclared conditions from one geometry pair."""

    identity = firewall.assert_access(geometry_seed, measurement_seed, repeat_index)
    map_geometry = build_scene_geometry(
        development_protocol,
        firewall,
        scene_variant,
        identity.geometry_seed,
        identity.measurement_seed,
        identity.repeat_index,
        "map",
    )
    scan_geometry = build_scene_geometry(
        development_protocol,
        firewall,
        scene_variant,
        identity.geometry_seed,
        identity.measurement_seed,
        identity.repeat_index,
        "scan",
    )
    reference_translation = np.asarray(
        development_protocol.section("scene_generation")["common"][
            "reference_pose_translation_world"
        ],
        dtype=np.float64,
    )
    reference_pose = np.array(
        [0.0, *reference_translation.tolist(), 0.0, 0.0, 0.0, 1.0],
        dtype=np.float64,
    )
    registration_config = _registration_config(development_protocol)
    block_id = (
        f"dev::{scene_variant}::g{identity.geometry_seed}::m{identity.measurement_seed}"
    )
    original_snapshot_id = f"{block_id}::r{identity.repeat_index:02d}"
    scene_id = f"dev::{scene_variant}::g{identity.geometry_seed}"
    bundles: list[AnchorAuditSnapshotBundle] = []
    for condition in noise_conditions(audit_protocol):
        firewall.assert_access(
            identity.geometry_seed, identity.measurement_seed, identity.repeat_index
        )
        scan_mask = (
            firewall.rng(
                scene_variant,
                identity.geometry_seed,
                identity.measurement_seed,
                identity.repeat_index,
                "scan_dropout",
            ).random(scan_geometry.points_world.shape[0])
            >= condition.scan_dropout_fraction
        )
        map_mask = (
            firewall.rng(
                scene_variant,
                identity.geometry_seed,
                identity.measurement_seed,
                identity.repeat_index,
                "map_dropout",
            ).random(map_geometry.points_world.shape[0])
            >= condition.map_dropout_fraction
        )
        scan_noise = firewall.rng(
            scene_variant,
            identity.geometry_seed,
            identity.measurement_seed,
            identity.repeat_index,
            "scan_noise",
        ).normal(
            0.0,
            condition.scan_noise_sigma_m,
            size=scan_geometry.points_world.shape,
        )
        map_noise = firewall.rng(
            scene_variant,
            identity.geometry_seed,
            identity.measurement_seed,
            identity.repeat_index,
            "map_noise",
        ).normal(
            0.0,
            condition.map_noise_sigma_m,
            size=map_geometry.points_world.shape,
        )
        scan_sensor = (
            scan_geometry.points_world - reference_translation + scan_noise
        )[scan_mask]
        noisy_map = (map_geometry.points_world + map_noise)[map_mask]
        scan_checksum = canonical_array_sha256(scan_sensor)
        map_checksum = canonical_array_sha256(noisy_map)
        scan_mask_checksum = canonical_array_sha256(scan_mask)
        map_mask_checksum = canonical_array_sha256(map_mask)
        dropout_checksum = canonical_sha256(
            {
                "scan_dropout_mask": scan_mask_checksum,
                "map_dropout_mask": map_mask_checksum,
            }
        )
        snapshot_id = (
            original_snapshot_id
            if condition.condition_id == "LOCKED_FULL_NOISE"
            else f"anchor::{condition.condition_id}::{original_snapshot_id}"
        )
        base_checksum = canonical_sha256(
            {
                "base_snapshot_id": snapshot_id,
                "scan_checksum": scan_checksum,
                "map_checksum": map_checksum,
                "dropout_checksum": dropout_checksum,
                "reference_pose": reference_pose,
                "registration_configuration": registration_config,
            }
        )
        metadata = {
            "scene_variant": str(scene_variant),
            "geometry_seed": identity.geometry_seed,
            "measurement_seed": identity.measurement_seed,
            "repeat_index": identity.repeat_index,
            "base_snapshot_checksum": base_checksum,
            "audit_measurement_condition": condition.condition_id,
        }
        assert_optimizer_snapshot_metadata_safe(metadata)
        snapshot = RegistrationSnapshot(
            snapshot_id=snapshot_id,
            scan_points=scan_sensor,
            local_map_points=noisy_map,
            reference_pose=reference_pose,
            registration_config=registration_config,
            metadata=metadata,
        )
        bundles.append(
            AnchorAuditSnapshotBundle(
                snapshot=snapshot,
                scene_id=scene_id,
                scene_variant=str(scene_variant),
                geometry_seed=identity.geometry_seed,
                measurement_seed=identity.measurement_seed,
                repeat_index=identity.repeat_index,
                block_id=block_id,
                base_snapshot_id=original_snapshot_id,
                condition_id=condition.condition_id,
                base_snapshot_checksum=base_checksum,
                scan_checksum=scan_checksum,
                map_checksum=map_checksum,
                dropout_checksum=dropout_checksum,
            )
        )
    return tuple(bundles)


def robust_gradient(evaluation: RegistrationEvaluation, huber_delta_m: float) -> np.ndarray:
    residual = np.asarray(evaluation.residual, dtype=np.float64)
    jacobian = np.asarray(evaluation.jacobian, dtype=np.float64)
    absolute = np.abs(residual)
    weights = np.ones_like(absolute)
    outside = absolute > float(huber_delta_m)
    weights[outside] = float(huber_delta_m) / absolute[outside]
    return jacobian.T @ (weights * residual)


def plane_fit_checksum(evaluation: RegistrationEvaluation) -> str:
    return canonical_sha256(
        {
            "plane_normals": np.asarray(evaluation.plane_normals),
            "plane_centroids": np.asarray(evaluation.plane_centroids),
        }
    )


def pose_distance(first: np.ndarray, second: np.ndarray) -> tuple[float, float]:
    return (
        translation_error_m(first, second),
        rotation_geodesic_error_rad(first, second),
    )


def pose_json(value: np.ndarray) -> str:
    return json.dumps(
        np.asarray(value, dtype=np.float64).tolist(),
        separators=(",", ":"),
        allow_nan=False,
    )


def pose_from_json(value: str) -> np.ndarray:
    result = np.asarray(json.loads(str(value)), dtype=np.float64)
    if result.shape not in {(8,), (4, 4)}:
        raise ValueError("serialized pose has invalid shape")
    return result


def _success_thresholds(snapshot: RegistrationSnapshot) -> tuple[float, float]:
    success = snapshot.registration_config["success"]
    return (
        float(success["translation_error_threshold_m"]),
        float(success["rotation_geodesic_error_threshold_rad"]),
    )


def outcome_success(
    snapshot: RegistrationSnapshot, outcome: RegistrationOutcome
) -> tuple[bool, float, float]:
    translation, rotation = pose_distance(outcome.final_pose, snapshot.reference_pose)
    translation_threshold, rotation_threshold = _success_thresholds(snapshot)
    finite = bool(
        outcome.finite_result
        and math.isfinite(translation)
        and math.isfinite(rotation)
        and math.isfinite(outcome.final_evaluation.cost)
    )
    success = evaluate_recovery_success(
        translation,
        rotation,
        solver_converged=outcome.solver_converged,
        finite_result=finite,
        iteration_limit_not_failed=outcome.iteration_limit_not_failed,
        translation_success_threshold_m=translation_threshold,
        rotation_success_threshold_rad=rotation_threshold,
    )
    return success, translation, rotation


def _run_outcome(
    method: str,
    snapshot: RegistrationSnapshot,
    seed: int,
    prepared: PreparedFullReassociationSession,
    baseline: FrozenJacobianBaseline,
) -> tuple[RegistrationOutcome, float]:
    started = time.perf_counter()
    if method == "full_reassociation":
        outcome = run_prepared_full_reassociation_core(
            prepared, snapshot.reference_pose, seed
        )
    elif method == "frozen_jacobian":
        outcome = run_frozen_jacobian_core(
            baseline,
            snapshot.reference_pose,
            snapshot.registration_config,
            seed,
        )
    else:
        raise ValueError(f"unknown zero-audit method: {method}")
    return outcome, (time.perf_counter() - started) * 1000.0


def run_zero_registration(
    bundle: AnchorAuditSnapshotBundle,
    method: str,
    seed: int,
    audit_protocol: AnchorAuditProtocol,
    *,
    deterministic_recheck: bool,
    prepared: PreparedFullReassociationSession | None = None,
    baseline: FrozenJacobianBaseline | None = None,
) -> dict[str, Any]:
    snapshot = bundle.snapshot
    if prepared is None:
        prepared = prepare_full_reassociation_session(
            snapshot.scan_points,
            snapshot.local_map_points,
            snapshot.registration_config,
            snapshot_id=snapshot.snapshot_id,
            reference_pose=snapshot.reference_pose,
        )
    if baseline is None:
        baseline = prepare_frozen_linearization(
            snapshot.scan_points,
            snapshot.local_map_points,
            snapshot.reference_pose,
            snapshot.registration_config,
            seed,
            snapshot_id=snapshot.snapshot_id,
        )
    outcome, runtime_ms = _run_outcome(
        method, snapshot, seed, prepared, baseline
    )
    success, translation_shift, rotation_shift = outcome_success(snapshot, outcome)
    options = registration_options(snapshot.registration_config)
    gradient = robust_gradient(outcome.initial_evaluation, options.huber_delta_m)
    gradient_norm = float(np.linalg.norm(gradient))
    normalized_gradient_norm = gradient_norm / math.sqrt(
        max(outcome.initial_evaluation.correspondence_count, 1)
    )
    try:
        first_delta = _solve_robust_step(
            outcome.initial_evaluation.jacobian,
            outcome.initial_evaluation.residual,
            options,
        )
        first_pose = boxplus_pose(snapshot.reference_pose, first_delta)
        first_translation, first_rotation = pose_distance(
            first_pose, snapshot.reference_pose
        )
    except (ValueError, np.linalg.LinAlgError):
        first_translation = float("nan")
        first_rotation = float("nan")

    recheck_translation = None
    recheck_rotation = None
    recheck_pass = None
    recheck_final_pose = None
    if deterministic_recheck:
        recheck, _ = _run_outcome(method, snapshot, seed, prepared, baseline)
        recheck_translation, recheck_rotation = pose_distance(
            recheck.final_pose, outcome.final_pose
        )
        tolerance = float(
            audit_protocol.section("formal_zero_audit")[
                "deterministic_pose_difference_tolerance"
            ]
        )
        recheck_pass = bool(
            recheck_translation <= tolerance and recheck_rotation <= tolerance
        )
        recheck_final_pose = pose_json(recheck.final_pose)

    fixed = audit_protocol.section("fixed_point_audit")
    shift_above = bool(
        translation_shift > float(fixed["stable_final_translation_tolerance_m"])
        or rotation_shift > float(fixed["stable_final_rotation_tolerance_rad"])
    )
    reference_not_fixed = bool(
        gradient_norm > float(fixed["robust_gradient_norm_tolerance"])
        and recheck_pass is True
        and shift_above
    )
    initial_plane_checksum = plane_fit_checksum(outcome.initial_evaluation)
    final_plane_checksum = plane_fit_checksum(outcome.final_evaluation)
    trace = tuple(outcome.counters.correspondence_checksums)
    checksum_changes = sum(left != right for left, right in zip(trace, trace[1:]))
    finite_output = bool(
        outcome.finite_result
        and np.all(np.isfinite(outcome.final_pose))
        and math.isfinite(outcome.final_evaluation.cost)
    )
    return {
        "scene_id": bundle.scene_id,
        "scene_variant": bundle.scene_variant,
        "geometry_seed": bundle.geometry_seed,
        "measurement_seed": bundle.measurement_seed,
        "repeat_index": bundle.repeat_index,
        "block_id": bundle.block_id,
        "base_snapshot_id": bundle.base_snapshot_id,
        "condition_id": bundle.condition_id,
        "method": method,
        "signed_amplitude": 0.0,
        "reference_pose": pose_json(snapshot.reference_pose),
        "zero_initial_pose": pose_json(snapshot.reference_pose),
        "zero_final_pose": pose_json(outcome.final_pose),
        "zero_translation_shift_from_reference_m": translation_shift,
        "zero_rotation_shift_from_reference_rad": rotation_shift,
        "zero_initial_cost": outcome.initial_evaluation.cost,
        "zero_final_cost": outcome.final_evaluation.cost,
        "zero_cost_change": outcome.final_evaluation.cost
        - outcome.initial_evaluation.cost,
        "zero_gradient_norm_at_reference": gradient_norm,
        "zero_gradient_norm_per_sqrt_correspondence": normalized_gradient_norm,
        "zero_first_step_translation_m": first_translation,
        "zero_first_step_rotation_rad": first_rotation,
        "zero_correspondence_count_initial": outcome.initial_evaluation.correspondence_count,
        "zero_correspondence_count_final": outcome.final_evaluation.correspondence_count,
        "zero_correspondence_checksum_initial": outcome.initial_evaluation.correspondence_checksum,
        "zero_correspondence_checksum_final": outcome.final_evaluation.correspondence_checksum,
        "zero_correspondence_checksum_change_count": checksum_changes,
        "zero_correspondence_changed": (
            outcome.initial_evaluation.correspondence_checksum
            != outcome.final_evaluation.correspondence_checksum
        ),
        "zero_plane_checksum_initial": initial_plane_checksum,
        "zero_plane_checksum_final": final_plane_checksum,
        "zero_plane_fit_changed": initial_plane_checksum != final_plane_checksum,
        "zero_iteration_count": outcome.iteration_count,
        "zero_solver_converged": outcome.solver_converged,
        "zero_finite_output": finite_output,
        "zero_iteration_limit_not_failed": outcome.iteration_limit_not_failed,
        "zero_termination_reason": outcome.termination_reason,
        "zero_failure_reason": outcome.failure_reason,
        "zero_success_under_current_gt_rule": success,
        "zero_runtime_ms": runtime_ms,
        "deterministic_recheck_performed": deterministic_recheck,
        "deterministic_recheck_final_pose": recheck_final_pose,
        "deterministic_recheck_translation_difference_m": recheck_translation,
        "deterministic_recheck_rotation_difference_rad": recheck_rotation,
        "deterministic_recheck_pass": recheck_pass,
        "reference_pose_not_registration_fixed_point": reference_not_fixed,
        "base_snapshot_checksum": bundle.base_snapshot_checksum,
        "scan_checksum": bundle.scan_checksum,
        "map_checksum": bundle.map_checksum,
        "dropout_checksum": bundle.dropout_checksum,
    }


def absolute_accuracy_valid(
    translation_error: float,
    rotation_error: float,
    audit_protocol: AnchorAuditProtocol,
) -> bool:
    section = audit_protocol.section("anchor_candidates")
    return bool(
        math.isfinite(float(translation_error))
        and math.isfinite(float(rotation_error))
        and float(translation_error)
        <= float(section["absolute_translation_threshold_m"])
        and float(rotation_error)
        <= float(section["absolute_rotation_threshold_rad"])
    )


def common_anchor_eligible(
    frozen_pose: np.ndarray,
    full_anchor_pose: np.ndarray,
    audit_protocol: AnchorAuditProtocol,
) -> tuple[bool, float, float]:
    translation, rotation = pose_distance(frozen_pose, full_anchor_pose)
    section = audit_protocol.section("common_anchor")
    eligible = bool(
        translation <= float(section["translation_eligibility_threshold_m"])
        and rotation <= float(section["rotation_eligibility_threshold_rad"])
    )
    return eligible, translation, rotation


def repeat_cluster_count(
    poses: Sequence[np.ndarray], audit_protocol: AnchorAuditProtocol
) -> int:
    values = tuple(np.asarray(pose, dtype=np.float64) for pose in poses)
    if not values:
        return 0
    section = audit_protocol.section("anchor_candidates")
    translation_threshold = float(section["repeat_cluster_translation_link_m"])
    rotation_threshold = float(section["repeat_cluster_rotation_link_rad"])
    parents = list(range(len(values)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left in range(len(values)):
        for right in range(left + 1, len(values)):
            translation, rotation = pose_distance(values[left], values[right])
            if translation <= translation_threshold and rotation <= rotation_threshold:
                union(left, right)
    return len({find(index) for index in range(len(values))})


def classify_d50_zero_root_cause(
    facts: Mapping[str, bool], audit_protocol: AnchorAuditProtocol
) -> tuple[str, tuple[str, ...]]:
    section = audit_protocol.section("d50_zero_root_cause")
    precedence = tuple(str(value) for value in section["primary_reason_precedence"])
    if set(precedence) != set(ROOT_CAUSE_VALUES):
        raise ValueError("d50-zero root-cause vocabulary changed")
    active = tuple(reason for reason in precedence if bool(facts.get(reason, False)))
    primary = active[0] if active else "UNKNOWN"
    secondary = tuple(reason for reason in active[1:] if reason != "UNKNOWN")
    if primary not in ROOT_CAUSE_VALUES or any(reason not in ROOT_CAUSE_VALUES for reason in secondary):
        raise ValueError("invalid d50-zero root-cause classification")
    return primary, secondary


def exact_file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ANCHOR_AUDIT_YAML_RELATIVE",
    "EXPECTED_CANDIDATES",
    "EXPECTED_CONDITIONS",
    "ROOT_CAUSE_VALUES",
    "AnchorAuditProtocol",
    "AnchorAuditSnapshotBundle",
    "NoiseCondition",
    "absolute_accuracy_valid",
    "assert_optimizer_snapshot_metadata_safe",
    "build_anchor_condition_snapshots",
    "classify_d50_zero_root_cause",
    "common_anchor_eligible",
    "exact_file_sha256",
    "load_anchor_audit_protocol",
    "noise_conditions",
    "outcome_success",
    "plane_fit_checksum",
    "pose_distance",
    "pose_from_json",
    "pose_json",
    "repeat_cluster_count",
    "robust_gradient",
    "run_zero_registration",
]
