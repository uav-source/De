"""Read-only loader and prospective helpers for the Day 2 v1.1 protocol.

The archived v1.0 files remain the base contract.  This module never rewrites or
deep-merges them; it exposes the base and amendment as two immutable mappings and
implements only deterministic, result-free helpers needed to validate the v1.1
lock before any Development or Test seed can be consumed.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


BASE_YAML_RELATIVE = Path("configs/capture_range/day2_synthetic_locked.yaml")
BASE_MARKDOWN_RELATIVE = Path("docs/directional_capture_range_day2_protocol.md")
AMENDMENT_YAML_RELATIVE = Path(
    "configs/capture_range/day2_protocol_amendment_v1_1.yaml"
)
AMENDMENT_MARKDOWN_RELATIVE = Path(
    "docs/directional_capture_range_day2_protocol_amendment_v1_1.md"
)

BASE_YAML_SHA256 = (
    "3b2f007c1d68d2399493ce5e15775120c4936495e4c08ef3fd0df1a88c35db65"
)
BASE_MARKDOWN_SHA256 = (
    "765f3eb755db18559fa0a83a1729512f2123b9ce658169542491faecc59e7bd4"
)
AMENDMENT_YAML_SHA256 = (
    "f2d68cbe467d617e013c19b6436bda8fc78744e0c8a3e26a76cf3bec654360d5"
)
AMENDMENT_MARKDOWN_SHA256 = (
    "8121e3d73110e7f367a0252c6f4654ba47a3073a784c19af3fd626d75d0d1c22"
)
BASE_LOCK_COMMIT = "04a20dd9fc4174558bba1f631358c6bd33ae870d"
BASE_LOCK_TAG = "archive/directional-capture-range-day2-protocol-lock"
AMENDMENT_LOCK_TAG = "archive/directional-capture-range-day2-protocol-v1.1-lock"

PROTOCOL_AMENDMENT_MANIFEST_FIELDS = MappingProxyType(
    {
        "protocol_amendment_reason": "v1_0_was_not_uniquely_executable",
        "protocol_amendment_timing": (
            "before_any_day2_development_or_test_run"
        ),
        "seed_consumed_before_amendment": False,
    }
)

SCENE_VARIANT_ORDER = (
    "GEOMETRY_RICH_ROOM",
    "LONG_CORRIDOR",
    "PARALLEL_WALLS",
    "END_FACE_TRANSITION_PRESENT",
    "END_FACE_TRANSITION_WEAK",
    "END_FACE_TRANSITION_ABSENT",
    "REPEATED_STRUCTURE",
)

AMENDMENT_ROOT_SECTIONS = (
    "amendment",
    "direction_inventory_resolution",
    "scene_generation_semantics",
    "test_block_and_scene_aggregation",
    "rich_room_bootstrap_resolution",
    "full_vs_frozen_stable_sign_resolution",
    "repeatability_cv_resolution",
    "candidate_search_hessian_resolution",
    "manual_review_resolution",
    "implementation_block_resolution",
)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """YAML loader that refuses silently shadowed mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_unique_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid Day 2 protocol YAML: {path}") from exc
    if type(value) is not dict:
        raise ValueError(f"Day 2 protocol root must be a mapping: {path}")
    return value


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({str(key): _freeze(child) for key, child in value.items()})
    if type(value) is list:
        return tuple(_freeze(child) for child in value)
    return value


@dataclass(frozen=True)
class EffectiveDay2Protocol:
    """Immutable v1.0 base plus the separately preserved v1.1 amendment."""

    base: Mapping[str, Any]
    amendment: Mapping[str, Any]
    manifest_fields: Mapping[str, Any]

    def resolution(self, section: str) -> Mapping[str, Any]:
        value = self.amendment.get(str(section))
        if not isinstance(value, Mapping):
            raise KeyError(f"unknown Day 2 amendment resolution: {section}")
        return value


def load_effective_day2_protocol(root: str | Path) -> EffectiveDay2Protocol:
    """Load and byte-validate the immutable v1.0 + v1.1 protocol pair."""

    repository = Path(root).resolve()
    paths_and_hashes = (
        (BASE_YAML_RELATIVE, BASE_YAML_SHA256),
        (BASE_MARKDOWN_RELATIVE, BASE_MARKDOWN_SHA256),
        (AMENDMENT_YAML_RELATIVE, AMENDMENT_YAML_SHA256),
        (AMENDMENT_MARKDOWN_RELATIVE, AMENDMENT_MARKDOWN_SHA256),
    )
    for relative_path, expected in paths_and_hashes:
        actual = file_sha256(repository / relative_path)
        if actual != expected:
            raise ValueError(
                f"Day 2 protocol byte hash changed for {relative_path}: {actual}"
            )

    base = _load_unique_yaml(repository / BASE_YAML_RELATIVE)
    amendment = _load_unique_yaml(repository / AMENDMENT_YAML_RELATIVE)
    _validate_amendment_linkage(base, amendment)
    return EffectiveDay2Protocol(
        base=_freeze(base),
        amendment=_freeze(amendment),
        manifest_fields=PROTOCOL_AMENDMENT_MANIFEST_FIELDS,
    )


def _validate_amendment_linkage(
    base: Mapping[str, Any], amendment: Mapping[str, Any]
) -> None:
    if tuple(amendment) != AMENDMENT_ROOT_SECTIONS:
        raise ValueError("Day 2 v1.1 amendment root sections changed")
    metadata = amendment.get("amendment")
    if type(metadata) is not dict:
        raise ValueError("Day 2 v1.1 amendment metadata missing")
    if metadata.get("version") != "1.1.0":
        raise ValueError("Day 2 v1.1 amendment version changed")
    if metadata.get("status") != (
        "prospectively_frozen_before_any_day2_development_or_test_run"
    ):
        raise ValueError("Day 2 v1.1 prospective status changed")
    linked = metadata.get("base_protocol")
    expected_link = {
        "yaml_path": str(BASE_YAML_RELATIVE),
        "yaml_sha256": BASE_YAML_SHA256,
        "markdown_path": str(BASE_MARKDOWN_RELATIVE),
        "markdown_sha256": BASE_MARKDOWN_SHA256,
        "lock_commit": BASE_LOCK_COMMIT,
        "lock_tag": BASE_LOCK_TAG,
    }
    if linked != expected_link:
        raise ValueError("Day 2 v1.1 base-protocol linkage changed")
    if base.get("protocol", {}).get("version") != "1.0.0":
        raise ValueError("Day 2 v1.0 base version changed")


@dataclass(frozen=True)
class SceneVariantSpec:
    key: str
    scene_id: str
    scene_variant: str
    weak_direction: tuple[float, float, float] | None
    strong_directions: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class DirectionDeclaration:
    declaration_id: str
    scene_id: str
    scene_variant: str
    role: str
    raw_vector: tuple[float, float, float]
    normalized_vector: tuple[float, float, float]
    retained_direction_id: str
    alias_of: str | None


@dataclass(frozen=True)
class RetainedDirection:
    scene_id: str
    scene_variant: str
    direction_id: str
    raw_vector: tuple[float, float, float]
    normalized_vector: tuple[float, float, float]
    direction_source: str
    declaration_ids: tuple[str, ...]


@dataclass(frozen=True)
class DirectionResolution:
    declarations: tuple[DirectionDeclaration, ...]
    retained_directions: tuple[RetainedDirection, ...]


def scene_variant_specs(
    protocol: EffectiveDay2Protocol,
) -> tuple[SceneVariantSpec, ...]:
    scenes = protocol.base["scene_generator"]

    def vectors(values: Sequence[Sequence[float]]) -> tuple[tuple[float, float, float], ...]:
        return tuple(tuple(float(component) for component in value) for value in values)

    rows: list[SceneVariantSpec] = []
    rich = scenes["geometry_rich_room"]
    rows.append(
        SceneVariantSpec(
            "GEOMETRY_RICH_ROOM",
            str(rich["scene_id"]),
            "GEOMETRY_RICH_ROOM",
            None,
            vectors(rich["theoretical_strong_directions"]),
        )
    )
    for key, config_key in (
        ("LONG_CORRIDOR", "long_corridor"),
        ("PARALLEL_WALLS", "parallel_walls"),
    ):
        scene = scenes[config_key]
        rows.append(
            SceneVariantSpec(
                key,
                str(scene["scene_id"]),
                key,
                tuple(float(value) for value in scene["theoretical_weak_direction"]),
                vectors(scene["theoretical_strong_directions"]),
            )
        )
    transition = scenes["end_face_transition"]
    for variant in ("PRESENT", "WEAK", "ABSENT"):
        weak = transition["theoretical_weak_direction_by_variant"][variant]
        rows.append(
            SceneVariantSpec(
                f"END_FACE_TRANSITION_{variant}",
                str(transition["scene_id"]),
                f"END_FACE_TRANSITION_{variant}",
                None if weak is None else tuple(float(value) for value in weak),
                vectors(transition["theoretical_strong_directions"]),
            )
        )
    repeated = scenes["repeated_structure"]
    rows.append(
        SceneVariantSpec(
            "REPEATED_STRUCTURE",
            str(repeated["scene_id"]),
            "REPEATED_STRUCTURE",
            tuple(float(value) for value in repeated["theoretical_weak_direction"]),
            vectors(repeated["theoretical_strong_directions"]),
        )
    )
    if tuple(row.key for row in rows) != SCENE_VARIANT_ORDER:
        raise ValueError("Day 2 scene-variant order changed")
    return tuple(rows)


@dataclass(frozen=True)
class _CandidateDeclaration:
    declaration_id: str
    role: str
    source: str
    preferred_direction_id: str
    raw_vector: tuple[float, float, float]


def resolve_scene_directions(
    protocol: EffectiveDay2Protocol, scene: SceneVariantSpec
) -> DirectionResolution:
    """Resolve declarations in memory without writing the formal inventory."""

    base_directions = protocol.base["direction_set"]["base_directed_axes"]
    icosahedron = protocol.base["direction_set"]["supplemental_sphere"]["raw_vectors"]
    threshold = float(
        protocol.amendment["direction_inventory_resolution"]["inventory_schema"]
        ["retained_directions"]["tolerance_abs_dot_same_orientation"]
    )

    candidates: list[_CandidateDeclaration] = []
    for row in base_directions:
        candidates.append(
            _candidate(scene, "base_directed_axis", "base_directed_axis", str(row["id"]), row["vector"])
        )
    if scene.weak_direction is not None:
        candidates.extend(
            _signed_axis_candidates(
                scene, "scene_weak_axis", "scene_weak_axis", scene.weak_direction
            )
        )
    strong_role = (
        "rich_room_control_axis"
        if scene.key == "GEOMETRY_RICH_ROOM"
        else "scene_strong_axis"
    )
    for vector in scene.strong_directions:
        candidates.extend(
            _signed_axis_candidates(
                scene, strong_role, "scene_strong_axis", vector
            )
        )
    for index, vector in enumerate(icosahedron):
        candidates.append(
            _candidate(
                scene,
                "supplemental_icosahedron",
                "supplemental_icosahedron",
                f"ico_{index:02d}",
                vector,
            )
        )

    retained_working: list[dict[str, Any]] = []
    declarations: list[DirectionDeclaration] = []
    for candidate in candidates:
        normalized = _normalized(candidate.raw_vector)
        duplicate = next(
            (
                row
                for row in retained_working
                if _dot(normalized, row["normalized_vector"]) >= threshold
            ),
            None,
        )
        if duplicate is None:
            retained_id = candidate.preferred_direction_id
            duplicate = {
                "direction_id": retained_id,
                "raw_vector": candidate.raw_vector,
                "normalized_vector": normalized,
                "direction_source": candidate.source,
                "declaration_ids": [candidate.declaration_id],
            }
            retained_working.append(duplicate)
            alias_of = None
        else:
            retained_id = str(duplicate["direction_id"])
            duplicate["declaration_ids"].append(candidate.declaration_id)
            alias_of = retained_id
        declarations.append(
            DirectionDeclaration(
                declaration_id=candidate.declaration_id,
                scene_id=scene.scene_id,
                scene_variant=scene.scene_variant,
                role=candidate.role,
                raw_vector=candidate.raw_vector,
                normalized_vector=normalized,
                retained_direction_id=retained_id,
                alias_of=alias_of,
            )
        )

    retained = tuple(
        RetainedDirection(
            scene_id=scene.scene_id,
            scene_variant=scene.scene_variant,
            direction_id=str(row["direction_id"]),
            raw_vector=tuple(row["raw_vector"]),
            normalized_vector=tuple(row["normalized_vector"]),
            direction_source=str(row["direction_source"]),
            declaration_ids=tuple(row["declaration_ids"]),
        )
        for row in retained_working
    )
    return DirectionResolution(tuple(declarations), retained)


def resolve_all_scene_directions(
    protocol: EffectiveDay2Protocol,
) -> Mapping[str, DirectionResolution]:
    return MappingProxyType(
        {
            scene.key: resolve_scene_directions(protocol, scene)
            for scene in scene_variant_specs(protocol)
        }
    )


def _candidate(
    scene: SceneVariantSpec,
    role: str,
    source: str,
    preferred_direction_id: str,
    vector: Sequence[float],
) -> _CandidateDeclaration:
    raw = tuple(float(value) for value in vector)
    declaration_id = f"{scene.key}::{source}::{preferred_direction_id}"
    return _CandidateDeclaration(
        declaration_id, role, source, preferred_direction_id, raw
    )


def _signed_axis_candidates(
    scene: SceneVariantSpec,
    role: str,
    source: str,
    vector: Sequence[float],
) -> tuple[_CandidateDeclaration, _CandidateDeclaration]:
    positive = _normalized(vector)
    if not _is_cartesian_axis(positive):
        raise ValueError("Day 2 scene weak/strong direction is not Cartesian")
    negative = tuple(-value for value in positive)
    return (
        _candidate(scene, role, source, _cartesian_direction_id(positive), positive),
        _candidate(scene, role, source, _cartesian_direction_id(negative), negative),
    )


def _normalized(vector: Sequence[float]) -> tuple[float, float, float]:
    values = np.asarray(vector, dtype=float)
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise ValueError("Day 2 direction must be a finite 3-vector")
    norm = float(np.linalg.norm(values))
    if norm <= 1.0e-12:
        raise ValueError("Day 2 direction cannot be zero")
    return tuple(float(value) for value in values / norm)


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return float(np.dot(np.asarray(left, dtype=float), np.asarray(right, dtype=float)))


def _is_cartesian_axis(vector: Sequence[float]) -> bool:
    absolute = np.abs(np.asarray(vector, dtype=float))
    return bool(np.isclose(np.max(absolute), 1.0) and np.count_nonzero(absolute > 1.0e-12) == 1)


def _cartesian_direction_id(vector: Sequence[float]) -> str:
    values = np.asarray(vector, dtype=float)
    axis = int(np.argmax(np.abs(values)))
    prefix = "pos" if float(values[axis]) > 0.0 else "neg"
    return f"{prefix}_{('x', 'y', 'z')[axis]}"


def stable_nonzero_effect_sign(
    effects: Sequence[float | None],
    *,
    blocks_per_stratum: int,
    minimum_same_nonzero_sign_blocks: int,
    zero_tolerance: float,
) -> int | None:
    """Return +1/-1 for the uniquely frozen stable-sign rule, else ``None``."""

    if len(effects) != int(blocks_per_stratum):
        raise ValueError("stable-sign input must contain every predeclared block")
    if minimum_same_nonzero_sign_blocks <= blocks_per_stratum // 2:
        raise ValueError("stable-sign majority must be strict")
    if zero_tolerance < 0.0 or not math.isfinite(zero_tolerance):
        raise ValueError("zero tolerance must be finite and nonnegative")
    positive = 0
    negative = 0
    for effect in effects:
        if effect is None:
            continue
        value = float(effect)
        if not math.isfinite(value):
            raise ValueError("effect values must be finite or null")
        positive += int(value > zero_tolerance)
        negative += int(value < -zero_tolerance)
    if positive >= minimum_same_nonzero_sign_blocks:
        return 1
    if negative >= minimum_same_nonzero_sign_blocks:
        return -1
    return None


def resolve_cv_value(
    *,
    finite_mean_d50: float,
    bootstrap_standard_deviation: float,
    uncensored_fraction: float,
    minimum_uncensored_fraction: float = 0.80,
    minimum_positive_mean_m: float = 1.0e-12,
) -> Mapping[str, Any]:
    """Apply only the v1.1 eligibility and zero-mean decision to precomputed stats."""

    mean = float(finite_mean_d50)
    standard_deviation = float(bootstrap_standard_deviation)
    fraction = float(uncensored_fraction)
    if not all(math.isfinite(value) for value in (mean, standard_deviation, fraction)):
        raise ValueError("CV inputs must be finite")
    if standard_deviation < 0.0 or not 0.0 <= fraction <= 1.0:
        raise ValueError("invalid CV standard deviation or uncensored fraction")
    result = {
        "mean_d50": mean,
        "bootstrap_standard_deviation": standard_deviation,
        "uncensored_fraction": fraction,
        "cv": None,
        "eligible": False,
        "reason": "",
    }
    if fraction < minimum_uncensored_fraction:
        result["reason"] = "INSUFFICIENT_UNCENSORED_FRACTION"
    elif mean <= minimum_positive_mean_m:
        result["reason"] = "ZERO_MEAN_D50"
    else:
        result["cv"] = standard_deviation / mean
        result["eligible"] = True
        result["reason"] = "ELIGIBLE"
    return MappingProxyType(result)


def production_translation_schur_callable():
    """Resolve, but do not execute, the existing production Schur helper."""

    from degen_detector.whitened_info import compute_translation_schur_info

    return compute_translation_schur_info


def require_manual_review_authority(
    status: str,
    reviewed_by: str | None,
    *,
    human_authorization_present: bool = False,
) -> None:
    """Reject a VALID assignment unless explicit human authority is present."""

    if str(status) != "VALID":
        return
    if not human_authorization_present:
        raise PermissionError("Codex may not assign manual review status VALID")
    if reviewed_by != "human_principal_investigator":
        raise PermissionError("VALID requires reviewed_by=human_principal_investigator")


__all__ = [
    "AMENDMENT_LOCK_TAG",
    "AMENDMENT_MARKDOWN_RELATIVE",
    "AMENDMENT_MARKDOWN_SHA256",
    "AMENDMENT_ROOT_SECTIONS",
    "AMENDMENT_YAML_RELATIVE",
    "AMENDMENT_YAML_SHA256",
    "BASE_LOCK_COMMIT",
    "BASE_LOCK_TAG",
    "BASE_MARKDOWN_RELATIVE",
    "BASE_MARKDOWN_SHA256",
    "BASE_YAML_RELATIVE",
    "BASE_YAML_SHA256",
    "DirectionDeclaration",
    "DirectionResolution",
    "EffectiveDay2Protocol",
    "PROTOCOL_AMENDMENT_MANIFEST_FIELDS",
    "RetainedDirection",
    "SCENE_VARIANT_ORDER",
    "SceneVariantSpec",
    "file_sha256",
    "load_effective_day2_protocol",
    "production_translation_schur_callable",
    "require_manual_review_authority",
    "resolve_all_scene_directions",
    "resolve_cv_value",
    "resolve_scene_directions",
    "scene_variant_specs",
    "stable_nonzero_effect_sign",
]
