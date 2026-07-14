"""Reusable infrastructure for paired weak-update experiments.

The experiment-specific module owns method definitions and gate policy.  This
module owns deterministic run layout, scene specifications, pairing keys,
aggregation, checksums, and geometry-block bootstrap mechanics.
"""

from __future__ import annotations

import hashlib
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence

import numpy as np

from eval.synthetic_pipeline_common import make_spec
from minibench.nested_geometry_observations import array_checksum
from minibench.observation_simulator import frame_planes, load_sequence


PAIR_FIELDS = (
    "sweep",
    "level",
    "stress",
    "geometry_seed",
    "sensor_seed",
    "process_seed",
)


def normalize_phase_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    output = dict(config)
    for field in ("geometry_seeds", "sensor_seeds", "process_seeds"):
        output[field] = [int(value) for value in config[field]]
    output["stress_names"] = [str(value) for value in config["stress_names"]]
    return output


def prepare_run_directories(
    data_run: Path,
    result_run: Path,
    resume: bool,
    overwrite: bool,
) -> None:
    existing = [path for path in (data_run, result_run) if path.exists()]
    if existing and overwrite:
        for path in existing:
            shutil.rmtree(path)
    elif existing and not resume:
        raise FileExistsError("run exists; use --resume or --overwrite")
    data_run.mkdir(parents=True, exist_ok=True)
    result_run.mkdir(parents=True, exist_ok=True)


def build_experiment_specs(
    common: Mapping[str, Any],
    geometry_seed: int,
    phase: str,
    experiment_family: str,
) -> list[Dict[str, Any]]:
    scene = common["scene"]
    control = make_spec(scene, "geometry", "OC", geometry_seed, phase, scene_family="OC")
    control["sequence_id"] = f"{experiment_family}_{phase}_open_control_G{geometry_seed}"
    specs = [control]
    for level, count in common["geometry_levels"].items():
        spec = make_spec(
            scene,
            "geometry",
            str(level),
            geometry_seed,
            phase,
            active_patch_count=int(count),
        )
        spec["sequence_id"] = f"{experiment_family}_{phase}_geometry_{level}_G{geometry_seed}"
        specs.append(spec)
    for level, probability in common["observation_levels"].items():
        spec = make_spec(
            scene,
            "observation",
            str(level),
            geometry_seed,
            phase,
            active_patch_count=int(scene["master_axial_patch_pool_size"]),
            keep_probability=float(probability),
        )
        spec["sequence_id"] = f"{experiment_family}_{phase}_observation_{level}_G{geometry_seed}"
        specs.append(spec)
    return specs


def observation_patch_ids(
    sequence_dir: Path,
    observations: Mapping[str, np.ndarray],
) -> np.ndarray:
    if "measurement_patch_ids" in observations:
        return np.asarray(observations["measurement_patch_ids"]).astype(str)
    sequence = load_sequence(sequence_dir)
    indices = np.asarray(observations["plane_indices"], dtype=int)
    output = np.empty(indices.shape, dtype="U64")
    for frame in range(indices.shape[0]):
        planes = frame_planes(sequence, frame)
        output[frame] = [planes[int(index)].plane_id for index in indices[frame]]
    return output


def observation_checksum(observations: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    fields = (
        "points_lidar",
        "normals_world",
        "plane_points_world",
        "r_list",
        "R_diag_list",
        "is_axial_support",
    )
    for field in fields:
        digest.update(field.encode("utf-8"))
        digest.update(array_checksum(np.asarray(observations[field])).encode("ascii"))
    return digest.hexdigest()


def sweep_name(spec: Mapping[str, Any]) -> str:
    return "open_control" if spec["level"] == "OC" else str(spec["sweep_type"])


def trial_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row[field] for field in PAIR_FIELDS)


def index_rows(
    rows: Sequence[Mapping[str, Any]],
    include_method: bool = False,
) -> Dict[tuple[Any, ...], Mapping[str, Any]]:
    output: Dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for row in rows:
        key = trial_key(row) + ((row["method"],) if include_method else ())
        if key in output:
            raise ValueError(f"duplicate trial key: {key}")
        output[key] = row
    return output


def relative_change(candidate: float, baseline: float) -> float:
    return (float(candidate) - float(baseline)) / max(abs(float(baseline)), 1.0e-12)


def median_relative_change(
    pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    metric: str,
) -> float:
    if not pairs:
        return float("nan")
    return float(
        np.median(
            [relative_change(float(left[metric]), float(right[metric])) for left, right in pairs]
        )
    )


def aggregate_method_trials(
    rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[str],
) -> list[Dict[str, Any]]:
    grouped: Dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    fields = ("sweep", "level", "stress", "geometry_seed", "sensor_seed", "method")
    for row in rows:
        grouped[tuple(row[field] for field in fields)].append(row)
    output = []
    for key, values in grouped.items():
        record = dict(zip(fields, key))
        record["process_trial_count"] = len(values)
        for metric in metrics:
            array = np.asarray([float(row[metric]) for row in values])
            record.update(
                {
                    f"{metric}_mean": float(np.mean(array)),
                    f"{metric}_median": float(np.median(array)),
                    f"{metric}_std": float(np.std(array)),
                    f"{metric}_iqr": float(np.quantile(array, 0.75) - np.quantile(array, 0.25)),
                    f"{metric}_q90": float(np.quantile(array, 0.90)),
                    f"{metric}_q95": float(np.quantile(array, 0.95)),
                }
            )
        output.append(record)
    return output


def map_paired_blocks(
    blocks: Sequence[Mapping[str, Any]],
    function: Callable[[Mapping[str, Any]], Any],
    workers: int,
):
    """Map independent blocks in input order while paired methods stay local."""

    if int(workers) == 1:
        return map(function, blocks)
    executor = ProcessPoolExecutor(max_workers=int(workers))

    def ordered_results():
        try:
            yield from executor.map(function, blocks)
        finally:
            executor.shutdown(wait=True)

    return ordered_results()


def block_bootstrap_effect(
    effects: Sequence[Mapping[str, Any]],
    repetitions: int,
    seed: int,
) -> Dict[str, Any]:
    grouped: Dict[int, list[float]] = defaultdict(list)
    for row in effects:
        grouped[int(row["geometry_seed"])].append(float(row["value"]))
    if not grouped:
        return {
            "estimate": float("nan"),
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "positive_geometry_ratio": float("nan"),
            "per_geometry": {},
        }
    seeds = sorted(grouped)
    per_geometry = {key: float(np.median(grouped[key])) for key in seeds}
    estimate = float(np.median([row["value"] for row in effects]))
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(int(repetitions)):
        sampled = rng.choice(seeds, size=len(seeds), replace=True)
        values = [value for geometry in sampled for value in grouped[int(geometry)]]
        samples.append(float(np.median(values)))
    return {
        "estimate": estimate,
        "ci_low": float(np.quantile(samples, 0.025)),
        "ci_high": float(np.quantile(samples, 0.975)),
        "positive_geometry_ratio": float(np.mean([value > 0.0 for value in per_geometry.values()])),
        "per_geometry": per_geometry,
    }
