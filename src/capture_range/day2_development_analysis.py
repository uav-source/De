"""Pure analysis primitives for exploratory Day 2 Development.

The functions in this module consume already-produced trial row mappings.  They
do not construct scenes, snapshots, registrations, or random measurement
realizations, which keeps Development seed access outside the analysis layer.
"""

from __future__ import annotations

import json
import math
import operator
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np

from .capture_radius import (
    capture_radius_from_fitted,
    fit_nonincreasing_isotonic,
    wilson_intervals,
)
from .day2_development_protocol import canonical_seed


TRANSLATION_AMPLITUDES_M = (0.00, 0.01, 0.02, 0.05, 0.10, 0.20, 0.40, 0.80)
ROTATION_AMPLITUDES_DEG = (0.00, 0.25, 0.50, 1.00, 2.00, 5.00, 10.00, 20.00)
DEFAULT_AMPLITUDES_BY_TYPE: Mapping[str, tuple[float, ...]] = MappingProxyType(
    {
        "translation": TRANSLATION_AMPLITUDES_M,
        "rotation": ROTATION_AMPLITUDES_DEG,
    }
)
REGISTRATION_PATHS = ("full_reassociation", "frozen_jacobian")
PREDECLARED_FULL_VS_FROZEN: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "END_FACE_TRANSITION_WEAK": ("pos_x", "neg_x"),
        "END_FACE_TRANSITION_ABSENT": ("pos_x", "neg_x"),
        "REPEATED_STRUCTURE": ("pos_x", "neg_x"),
    }
)


@dataclass(frozen=True, order=True)
class DevelopmentBlockKey:
    """A five-repeat analysis block; repeat index is deliberately absent."""

    scene_variant: str
    geometry_seed: int
    measurement_seed: int
    block_id: str


@dataclass(frozen=True, order=True)
class DevelopmentCurveKey:
    block: DevelopmentBlockKey
    perturbation_type: str
    direction_id: str
    registration_path: str


@dataclass(frozen=True)
class MonotonicityAudit:
    violation_indices: tuple[int, ...]
    violation_amplitude_pairs: tuple[tuple[float, float], ...]
    upward_probability_jumps: tuple[float, ...]

    @property
    def violation_count(self) -> int:
        return len(self.violation_indices)

    @property
    def raw_nonmonotonic(self) -> bool:
        return bool(self.violation_indices)

    @property
    def maximum_upward_jump(self) -> float:
        return max(self.upward_probability_jumps, default=0.0)


@dataclass(frozen=True)
class DevelopmentRecoveryCurve:
    key: DevelopmentCurveKey
    amplitudes: tuple[float, ...]
    successful_trials: tuple[int, ...]
    total_trials: tuple[int, ...]
    raw_probabilities: tuple[float, ...]
    wilson_lower: tuple[float, ...]
    wilson_upper: tuple[float, ...]
    isotonic_probabilities: tuple[float, ...]
    d50: float | None
    d90: float | None
    d50_right_censored: bool
    d90_right_censored: bool
    monotonicity: MonotonicityAudit
    repeat_indices: tuple[int, ...]
    success_by_amplitude_repeat: tuple[tuple[bool, ...], ...]
    correspondence_checksum_change_count: int


@dataclass(frozen=True)
class AxisRadius:
    axis: str
    positive_d50: float | None
    negative_d50: float | None
    conservative_exact_radius: float | None
    right_censored: bool
    lower_bound: float


@dataclass(frozen=True)
class AxisSeparationResult:
    key: DevelopmentCurveKey
    weak_axis: AxisRadius
    strong_axes: tuple[AxisRadius, AxisRadius]
    strong_radius: float
    separation: float | None
    block_evaluable: bool
    reason: str


@dataclass(frozen=True)
class FullVsFrozenDevelopmentResult:
    block: DevelopmentBlockKey
    scene_variant: str
    direction_id: str
    amplitudes: tuple[float, ...]
    raw_maximum_probability_gap: float
    raw_trapezoidal_integral_difference: float
    exact_d50_difference: float | None
    right_censoring_pattern: str
    correspondence_checksum_change_count: int
    descriptive_difference_observed: bool


@dataclass(frozen=True)
class BootstrapD50Result:
    key: DevelopmentCurveKey
    repetitions: int
    bootstrap_seed: int
    curve_subseed: int
    repeat_index_draws: tuple[tuple[int, ...], ...]
    d50_values: tuple[float | None, ...]
    uncensored_count: int
    uncensored_fraction: float
    finite_mean_d50: float | None
    sample_standard_deviation: float | None
    cv: float | None
    eligible: bool
    reason: str


def _strict_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool")
    if isinstance(value, str):
        try:
            integer = int(value)
        except ValueError as exc:
            raise TypeError(f"{name} must be an integer") from exc
        if str(integer) != value.strip():
            raise TypeError(f"{name} must be an integer")
        return integer
    try:
        return int(operator.index(value))
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer") from exc


def _strict_bool(value: Any, *, name: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
    raise TypeError(f"{name} must be boolean")


def _required(row: Mapping[str, Any], name: str) -> Any:
    if name not in row:
        raise ValueError(f"trial row is missing {name}")
    return row[name]


def _block_key(row: Mapping[str, Any]) -> DevelopmentBlockKey:
    scene = str(_required(row, "scene_variant"))
    geometry = _strict_int(_required(row, "geometry_seed"), name="geometry_seed")
    measurement = _strict_int(
        _required(row, "measurement_seed"), name="measurement_seed"
    )
    if not scene:
        raise ValueError("scene_variant cannot be empty")
    block_id = str(
        row.get("block_id", f"{scene}|g={geometry}|m={measurement}")
    )
    if not block_id:
        raise ValueError("block_id cannot be empty")
    return DevelopmentBlockKey(scene, geometry, measurement, block_id)


def _canonical_amplitude(value: Any, expected: Sequence[float]) -> float:
    amplitude = float(value)
    if not math.isfinite(amplitude) or amplitude < 0.0:
        raise ValueError("amplitude must be finite and non-negative")
    matches = [candidate for candidate in expected if amplitude == candidate]
    if len(matches) != 1:
        raise ValueError(f"unexpected Development amplitude: {amplitude!r}")
    return float(matches[0])


def _checksum_trace(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    decoded = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("correspondence checksum trace must be a JSON array") from exc
    if not isinstance(decoded, Sequence) or isinstance(
        decoded, (str, bytes, bytearray)
    ):
        raise ValueError("correspondence checksum trace must be a sequence")
    return tuple(str(item) for item in decoded)


def count_adjacent_checksum_changes(trace: Sequence[str]) -> int:
    """Count changes, not merely unique values, in one reassociation trace."""

    values = tuple(str(value) for value in trace)
    return sum(left != right for left, right in zip(values, values[1:]))


def aggregate_trial_rows(
    trial_rows: Iterable[Mapping[str, Any]],
    *,
    expected_repeats: int = 5,
    amplitudes_by_type: Mapping[str, Sequence[float]] = DEFAULT_AMPLITUDES_BY_TYPE,
    confidence_level: float = 0.95,
) -> tuple[DevelopmentRecoveryCurve, ...]:
    """Aggregate exact five-repeat/eight-amplitude Development curves.

    Rows are grouped by scene variant, geometry seed, measurement seed,
    perturbation type, physical directed direction ID, and registration path.
    Repeat index is an observation within a block and can never split a block.
    """

    repeats = _strict_int(expected_repeats, name="expected_repeats")
    if repeats <= 0:
        raise ValueError("expected_repeats must be positive")
    confidence = float(confidence_level)
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence_level must lie strictly between zero and one")

    expected_amplitudes: dict[str, tuple[float, ...]] = {}
    for perturbation_type, values in amplitudes_by_type.items():
        amplitudes = tuple(float(value) for value in values)
        if (
            len(amplitudes) != 8
            or len(set(amplitudes)) != 8
            or any(not math.isfinite(value) or value < 0.0 for value in amplitudes)
            or any(right <= left for left, right in zip(amplitudes, amplitudes[1:]))
        ):
            raise ValueError(
                f"{perturbation_type} must declare eight strictly increasing amplitudes"
            )
        expected_amplitudes[str(perturbation_type)] = amplitudes

    observations: dict[
        DevelopmentCurveKey, dict[float, dict[int, bool]]
    ] = {}
    checksum_changes: dict[DevelopmentCurveKey, int] = {}
    triple_to_id: dict[tuple[str, int, int], str] = {}
    id_to_triple: dict[str, tuple[str, int, int]] = {}
    row_count = 0
    for row_count, row in enumerate(trial_rows, start=1):
        if not isinstance(row, Mapping):
            raise TypeError("trial_rows must contain mappings")
        block = _block_key(row)
        triple = (block.scene_variant, block.geometry_seed, block.measurement_seed)
        previous_id = triple_to_id.setdefault(triple, block.block_id)
        if previous_id != block.block_id:
            raise ValueError("one Development block triple has multiple block_id values")
        previous_triple = id_to_triple.setdefault(block.block_id, triple)
        if previous_triple != triple:
            raise ValueError("one block_id identifies multiple Development block triples")

        perturbation_type = str(_required(row, "perturbation_type"))
        if perturbation_type not in expected_amplitudes:
            raise ValueError(f"unknown perturbation_type: {perturbation_type}")
        direction_id = str(_required(row, "direction_id"))
        if not direction_id:
            raise ValueError("direction_id cannot be empty")
        registration_path = str(_required(row, "registration_path"))
        if registration_path not in REGISTRATION_PATHS:
            raise ValueError(f"unknown registration_path: {registration_path}")
        amplitude = _canonical_amplitude(
            _required(row, "amplitude"), expected_amplitudes[perturbation_type]
        )
        repeat_index = _strict_int(
            _required(row, "repeat_index"), name="repeat_index"
        )
        if repeat_index < 0 or repeat_index >= repeats:
            raise ValueError(f"repeat_index must lie in [0,{repeats})")
        success = _strict_bool(_required(row, "success"), name="success")
        key = DevelopmentCurveKey(
            block, perturbation_type, direction_id, registration_path
        )
        per_repeat = observations.setdefault(key, {}).setdefault(amplitude, {})
        if repeat_index in per_repeat:
            raise ValueError(
                "duplicate trial row for block/type/direction/path/amplitude/repeat"
            )
        per_repeat[repeat_index] = success

        if "correspondence_checksum_change_count" in row:
            change_count = _strict_int(
                row["correspondence_checksum_change_count"],
                name="correspondence_checksum_change_count",
            )
            if change_count < 0:
                raise ValueError("correspondence checksum change count cannot be negative")
        else:
            trace = _checksum_trace(row.get("correspondence_checksum_trace"))
            change_count = count_adjacent_checksum_changes(trace)
        checksum_changes[key] = checksum_changes.get(key, 0) + change_count

    if row_count == 0:
        raise ValueError("trial_rows cannot be empty")

    curves: list[DevelopmentRecoveryCurve] = []
    expected_repeat_indices = tuple(range(repeats))
    for key in sorted(observations):
        amplitudes = expected_amplitudes[key.perturbation_type]
        by_amplitude = observations[key]
        if set(by_amplitude) != set(amplitudes):
            raise ValueError(f"curve {key} does not contain exactly eight amplitudes")
        success_matrix: list[tuple[bool, ...]] = []
        for amplitude in amplitudes:
            per_repeat = by_amplitude[amplitude]
            if tuple(sorted(per_repeat)) != expected_repeat_indices:
                raise ValueError(
                    f"curve {key} amplitude {amplitude} does not contain five repeats"
                )
            success_matrix.append(
                tuple(per_repeat[index] for index in expected_repeat_indices)
            )

        success_counts = np.asarray(
            [sum(values) for values in success_matrix], dtype=np.int64
        )
        total_counts = np.full(len(amplitudes), repeats, dtype=np.int64)
        raw = success_counts.astype(np.float64) / total_counts
        isotonic = fit_nonincreasing_isotonic(raw, total_counts.astype(np.float64))
        wilson_lower, wilson_upper = wilson_intervals(
            success_counts, total_counts, confidence
        )
        amplitude_array = np.asarray(amplitudes, dtype=np.float64)
        d50, d50_censored = capture_radius_from_fitted(
            amplitude_array, isotonic, 0.5
        )
        d90, d90_censored = capture_radius_from_fitted(
            amplitude_array, isotonic, 0.9
        )
        upward = np.diff(raw)
        violation_indices = tuple(
            int(index) for index in np.flatnonzero(upward > 0.0)
        )
        monotonicity = MonotonicityAudit(
            violation_indices=violation_indices,
            violation_amplitude_pairs=tuple(
                (amplitudes[index], amplitudes[index + 1])
                for index in violation_indices
            ),
            upward_probability_jumps=tuple(
                float(upward[index]) for index in violation_indices
            ),
        )
        curves.append(
            DevelopmentRecoveryCurve(
                key=key,
                amplitudes=amplitudes,
                successful_trials=tuple(int(value) for value in success_counts),
                total_trials=tuple(int(value) for value in total_counts),
                raw_probabilities=tuple(float(value) for value in raw),
                wilson_lower=tuple(float(value) for value in wilson_lower),
                wilson_upper=tuple(float(value) for value in wilson_upper),
                isotonic_probabilities=tuple(float(value) for value in isotonic),
                d50=d50,
                d90=d90,
                d50_right_censored=d50_censored,
                d90_right_censored=d90_censored,
                monotonicity=monotonicity,
                repeat_indices=expected_repeat_indices,
                success_by_amplitude_repeat=tuple(success_matrix),
                correspondence_checksum_change_count=checksum_changes[key],
            )
        )
    return tuple(curves)


def _axis_radius(
    curves_by_direction: Mapping[str, DevelopmentRecoveryCurve], axis: str
) -> AxisRadius:
    positive_id = f"pos_{axis}"
    negative_id = f"neg_{axis}"
    try:
        positive = curves_by_direction[positive_id]
        negative = curves_by_direction[negative_id]
    except KeyError as exc:
        raise ValueError(f"missing antipodal Development curve for axis {axis}") from exc
    if positive.amplitudes != negative.amplitudes:
        raise ValueError(f"antipodal amplitude grids differ for axis {axis}")
    exact = tuple(value for value in (positive.d50, negative.d50) if value is not None)
    right_censored = not exact
    conservative = min(exact) if exact else None
    lower_bound = (
        float(conservative)
        if conservative is not None
        else float(positive.amplitudes[-1])
    )
    return AxisRadius(
        axis=axis,
        positive_d50=positive.d50,
        negative_d50=negative.d50,
        conservative_exact_radius=conservative,
        right_censored=right_censored,
        lower_bound=lower_bound,
    )


def compute_axis_separation(
    curves: Iterable[DevelopmentRecoveryCurve],
    *,
    weak_axis: str = "x",
    strong_axes: tuple[str, str] = ("y", "z"),
    denominator_tolerance: float = 1.0e-12,
) -> AxisSeparationResult:
    """Apply the Development censored weak/strong-axis separation rules."""

    values = tuple(curves)
    if not values:
        raise ValueError("axis separation requires curves")
    common = values[0].key
    curves_by_direction: dict[str, DevelopmentRecoveryCurve] = {}
    for curve in values:
        key = curve.key
        if (
            key.block != common.block
            or key.perturbation_type != common.perturbation_type
            or key.registration_path != common.registration_path
        ):
            raise ValueError("axis separation curves must share block/type/path")
        if key.direction_id in curves_by_direction:
            raise ValueError(f"duplicate direction curve: {key.direction_id}")
        curves_by_direction[key.direction_id] = curve
    if common.perturbation_type != "translation":
        raise ValueError("Development axis separation is translation-only")
    if weak_axis in strong_axes or len(set(strong_axes)) != 2:
        raise ValueError("weak and two strong axes must be distinct")
    tolerance = float(denominator_tolerance)
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("denominator_tolerance must be finite and non-negative")

    weak = _axis_radius(curves_by_direction, weak_axis)
    strong = tuple(
        _axis_radius(curves_by_direction, axis) for axis in strong_axes
    )
    strong_pair = (strong[0], strong[1])
    strong_radius = float(np.median([axis.lower_bound for axis in strong_pair]))
    result_key = DevelopmentCurveKey(
        common.block, common.perturbation_type, f"axis_{weak_axis}", common.registration_path
    )
    if weak.right_censored:
        return AxisSeparationResult(
            result_key,
            weak,
            strong_pair,
            strong_radius,
            None,
            False,
            "WEAK_RADIUS_RIGHT_CENSORED",
        )
    if strong_radius <= tolerance:
        return AxisSeparationResult(
            result_key,
            weak,
            strong_pair,
            strong_radius,
            None,
            False,
            "NONPOSITIVE_STRONG_RADIUS",
        )
    assert weak.conservative_exact_radius is not None
    separation = 1.0 - weak.conservative_exact_radius / strong_radius
    return AxisSeparationResult(
        result_key,
        weak,
        strong_pair,
        strong_radius,
        float(separation),
        True,
        "EVALUABLE",
    )


def compare_full_vs_frozen(
    full: DevelopmentRecoveryCurve,
    frozen: DevelopmentRecoveryCurve,
    *,
    zero_tolerance: float = 1.0e-12,
) -> FullVsFrozenDevelopmentResult:
    """Compare raw curves; isotonic values enter only through exact d50."""

    if full.key.registration_path != "full_reassociation":
        raise ValueError("full curve must use full_reassociation")
    if frozen.key.registration_path != "frozen_jacobian":
        raise ValueError("frozen curve must use frozen_jacobian")
    if (
        full.key.block != frozen.key.block
        or full.key.perturbation_type != frozen.key.perturbation_type
        or full.key.direction_id != frozen.key.direction_id
    ):
        raise ValueError("full and frozen curves must share block/type/direction")
    if full.key.perturbation_type != "translation":
        raise ValueError("Development full-vs-frozen comparison is translation-only")
    if full.amplitudes != frozen.amplitudes:
        raise ValueError("full and frozen amplitude grids differ")
    tolerance = float(zero_tolerance)
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("zero_tolerance must be finite and non-negative")

    amplitudes = np.asarray(full.amplitudes, dtype=np.float64)
    raw_difference = np.asarray(full.raw_probabilities) - np.asarray(
        frozen.raw_probabilities
    )
    maximum_gap = float(np.max(np.abs(raw_difference)))
    signed_integral = float(
        np.sum(
            0.5
            * (raw_difference[:-1] + raw_difference[1:])
            * np.diff(amplitudes)
        )
    )
    full_censored = full.d50_right_censored
    frozen_censored = frozen.d50_right_censored
    if not full_censored and not frozen_censored:
        censor_pattern = "BOTH_EXACT"
        assert full.d50 is not None and frozen.d50 is not None
        exact_difference: float | None = float(full.d50 - frozen.d50)
    elif not full_censored and frozen_censored:
        censor_pattern = "FULL_EXACT_FROZEN_CENSORED"
        exact_difference = None
    elif full_censored and not frozen_censored:
        censor_pattern = "FULL_CENSORED_FROZEN_EXACT"
        exact_difference = None
    else:
        censor_pattern = "BOTH_CENSORED"
        exact_difference = None
    numeric_difference = maximum_gap > tolerance or (
        exact_difference is not None and abs(exact_difference) > tolerance
    )
    checksum_changes = full.correspondence_checksum_change_count
    return FullVsFrozenDevelopmentResult(
        block=full.key.block,
        scene_variant=full.key.block.scene_variant,
        direction_id=full.key.direction_id,
        amplitudes=full.amplitudes,
        raw_maximum_probability_gap=maximum_gap,
        raw_trapezoidal_integral_difference=signed_integral,
        exact_d50_difference=exact_difference,
        right_censoring_pattern=censor_pattern,
        correspondence_checksum_change_count=checksum_changes,
        descriptive_difference_observed=(
            numeric_difference and checksum_changes > 0
        ),
    )


def compare_predeclared_full_vs_frozen(
    curves: Iterable[DevelopmentRecoveryCurve],
) -> tuple[FullVsFrozenDevelopmentResult, ...]:
    """Compare only the three prospectively declared scene/direction strata."""

    paired: dict[
        tuple[DevelopmentBlockKey, str], dict[str, DevelopmentRecoveryCurve]
    ] = {}
    for curve in curves:
        scene = curve.key.block.scene_variant
        if (
            curve.key.perturbation_type != "translation"
            or scene not in PREDECLARED_FULL_VS_FROZEN
            or curve.key.direction_id not in PREDECLARED_FULL_VS_FROZEN[scene]
        ):
            continue
        key = (curve.key.block, curve.key.direction_id)
        paths = paired.setdefault(key, {})
        if curve.key.registration_path in paths:
            raise ValueError("duplicate curve in predeclared full-vs-frozen stratum")
        paths[curve.key.registration_path] = curve

    results: list[FullVsFrozenDevelopmentResult] = []
    for key in sorted(paired):
        paths = paired[key]
        if set(paths) != set(REGISTRATION_PATHS):
            raise ValueError(f"incomplete predeclared full-vs-frozen pair: {key}")
        results.append(
            compare_full_vs_frozen(
                paths["full_reassociation"], paths["frozen_jacobian"]
            )
        )
    return tuple(results)


def bootstrap_curve_subseed(
    curve: DevelopmentRecoveryCurve, *, bootstrap_seed: int = 161803
) -> int:
    seed = _strict_int(bootstrap_seed, name="bootstrap_seed")
    if seed < 0:
        raise ValueError("bootstrap_seed must be non-negative")
    return canonical_seed(
        {
            "bootstrap_seed": seed,
            "block_id": curve.key.block.block_id,
            "direction_id": curve.key.direction_id,
        }
    )


def bootstrap_full_translation_curve(
    curve: DevelopmentRecoveryCurve,
    *,
    repetitions: int = 500,
    bootstrap_seed: int = 161803,
    minimum_uncensored_fraction: float = 0.80,
    minimum_positive_mean: float = 1.0e-12,
) -> BootstrapD50Result:
    """Repeat-index bootstrap with one shared draw across all amplitudes."""

    if curve.key.perturbation_type != "translation":
        raise ValueError("repeatability bootstrap is translation-only")
    if curve.key.registration_path != "full_reassociation":
        raise ValueError("repeatability bootstrap is full-reassociation-only")
    count = _strict_int(repetitions, name="repetitions")
    if count <= 0:
        raise ValueError("repetitions must be positive")
    minimum_fraction = float(minimum_uncensored_fraction)
    minimum_mean = float(minimum_positive_mean)
    if not 0.0 <= minimum_fraction <= 1.0:
        raise ValueError("minimum_uncensored_fraction must lie in [0,1]")
    if not math.isfinite(minimum_mean) or minimum_mean < 0.0:
        raise ValueError("minimum_positive_mean must be finite and non-negative")

    matrix = np.asarray(curve.success_by_amplitude_repeat, dtype=np.bool_)
    repeat_count = len(curve.repeat_indices)
    if matrix.shape != (len(curve.amplitudes), repeat_count) or repeat_count != 5:
        raise ValueError("Development bootstrap requires an 8-by-5 success matrix")
    subseed = bootstrap_curve_subseed(curve, bootstrap_seed=bootstrap_seed)
    generator = np.random.Generator(np.random.PCG64(subseed))
    amplitude_array = np.asarray(curve.amplitudes, dtype=np.float64)
    weights = np.full(len(curve.amplitudes), repeat_count, dtype=np.float64)
    draws: list[tuple[int, ...]] = []
    d50_values: list[float | None] = []
    for _ in range(count):
        draw_array = generator.integers(
            0, repeat_count, size=repeat_count, endpoint=False
        )
        draw = tuple(int(value) for value in draw_array)
        draws.append(draw)
        raw = np.mean(matrix[:, draw_array], axis=1, dtype=np.float64)
        fitted = fit_nonincreasing_isotonic(raw, weights)
        d50, censored = capture_radius_from_fitted(
            amplitude_array, fitted, 0.5
        )
        d50_values.append(None if censored else d50)

    finite = np.asarray(
        [value for value in d50_values if value is not None], dtype=np.float64
    )
    uncensored_count = int(finite.size)
    uncensored_fraction = uncensored_count / count
    finite_mean = float(np.mean(finite)) if uncensored_count else None
    sample_standard_deviation = (
        float(np.std(finite, ddof=1)) if uncensored_count >= 2 else None
    )
    cv: float | None = None
    eligible = False
    if uncensored_count < 2:
        reason = "INSUFFICIENT_UNCENSORED_BOOTSTRAPS"
    elif uncensored_fraction < minimum_fraction:
        reason = "INSUFFICIENT_UNCENSORED_FRACTION"
    elif finite_mean is not None and finite_mean <= minimum_mean:
        reason = "ZERO_MEAN_D50"
    else:
        assert finite_mean is not None and sample_standard_deviation is not None
        cv = sample_standard_deviation / finite_mean
        eligible = True
        reason = "ELIGIBLE"
    return BootstrapD50Result(
        key=curve.key,
        repetitions=count,
        bootstrap_seed=_strict_int(bootstrap_seed, name="bootstrap_seed"),
        curve_subseed=subseed,
        repeat_index_draws=tuple(draws),
        d50_values=tuple(d50_values),
        uncensored_count=uncensored_count,
        uncensored_fraction=uncensored_fraction,
        finite_mean_d50=finite_mean,
        sample_standard_deviation=sample_standard_deviation,
        cv=cv,
        eligible=eligible,
        reason=reason,
    )


def bootstrap_full_translation_curves(
    curves: Iterable[DevelopmentRecoveryCurve],
    **kwargs: Any,
) -> tuple[BootstrapD50Result, ...]:
    """Bootstrap every and only full-reassociation translation curve."""

    eligible = sorted(
        (
            curve
            for curve in curves
            if curve.key.perturbation_type == "translation"
            and curve.key.registration_path == "full_reassociation"
        ),
        key=lambda curve: curve.key,
    )
    return tuple(
        bootstrap_full_translation_curve(curve, **kwargs) for curve in eligible
    )
