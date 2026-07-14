"""Shared synthetic-scene I/O and aggregation helpers.

The helpers in this module are stage-neutral.  Detector experiments may reuse
the scene and observation plumbing without importing a superseded evaluation
workflow.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np
import yaml

from minibench.observation_simulator import (
    save_observations,
    simulate_observation_degradation,
    simulate_sequence_observations,
)
from minibench.scene_generator import (
    generate_open_control,
    generate_straight_tunnel,
    load_scene_config,
    save_sequence,
)


def make_spec(
    scene: Mapping[str, Any],
    sweep_type: str,
    level: str,
    geometry_seed: int,
    split: str,
    scene_family: str = "ST",
    active_patch_count: int = 0,
    keep_probability: float | None = None,
) -> Dict[str, Any]:
    """Build a stage-neutral finite-scene experiment specification."""

    sequence_id = f"synthetic_{sweep_type}_{level}_G{geometry_seed}"
    spec: Dict[str, Any] = {
        "sequence_id": sequence_id,
        "sweep_type": sweep_type,
        "level": level,
        "split": split,
        "scene_family": scene_family,
        "difficulty": level,
        "seed_id": f"G{geometry_seed}",
        "motion_id": "M1",
        "random_seed": int(geometry_seed),
        "geometry_seed": int(geometry_seed),
        "axis": [1.0, 0.0, 0.0],
        "frames": int(scene["frames"]),
        "dt_s": float(scene["dt_s"]),
        "active_axial_patch_count": int(active_patch_count),
        "master_axial_patch_pool_size": int(scene["master_axial_patch_pool_size"]),
        "expected_degeneracy": f"{sweep_type}_{level}",
        "scientific_role": "open_control" if scene_family == "OC" else f"{sweep_type}_sweep",
    }
    if scene_family == "OC":
        spec.update(
            {
                "length_m": float(scene["open_length_m"]),
                "scene": {
                    "bounds_m": scene["open_bounds_m"],
                    "box_count": int(scene["open_box_count"]),
                },
            }
        )
        spec.pop("master_axial_patch_pool_size")
    else:
        spec.update(
            {
                "tunnel_length_m": float(scene["tunnel_length_m"]),
                "width_m": float(scene["width_m"]),
                "height_m": float(scene["height_m"]),
                "scene": {"finite_plane_patches": True},
            }
        )
    if keep_probability is not None:
        spec["axial_observation_keep_probability"] = float(keep_probability)
    return spec


def generate_or_validate_sequence(sequence_dir: Path, spec: Mapping[str, Any]) -> None:
    required = ["gt.tum", "axis.csv", "planes.csv", "scene_metadata.json", "resolved_scene_config.yaml"]
    if all((sequence_dir / name).exists() for name in required):
        return
    sequence_dir.mkdir(parents=True, exist_ok=True)
    config_path = sequence_dir / "resolved_scene_config.yaml"
    config_path.write_text(yaml.safe_dump(dict(spec), sort_keys=False), encoding="utf-8")
    resolved = load_scene_config(config_path)
    sequence = generate_open_control(resolved) if spec["scene_family"] == "OC" else generate_straight_tunnel(resolved)
    save_sequence(sequence, sequence_dir)
    metadata_path = sequence_dir / "scene_metadata.json"
    metadata = read_json(metadata_path)
    metadata.update(
        {
            "sweep_type": spec["sweep_type"],
            "level": spec["level"],
            "split": spec["split"],
            "gt_checksum": sha256_file(sequence_dir / "gt.tum"),
            "planes_checksum": sha256_file(sequence_dir / "planes.csv"),
            "axis_checksum": sha256_file(sequence_dir / "axis.csv"),
        }
    )
    geometry_payload = {
        key: metadata.get(key)
        for key in [
            "geometry_seed",
            "master_pool_checksum",
            "active_patch_ids",
            "geometry_axial_support_score",
            "non_axial_shell_checksum",
            "sampling_weight_checksum",
            "gt_checksum",
            "planes_checksum",
            "axis_checksum",
        ]
    }
    metadata["geometry_metadata_checksum"] = _sha256_json(geometry_payload)
    write_json(metadata_path, metadata)


def generate_or_load_observations(
    sensor_dir: Path,
    sequence_dir: Path,
    spec: Mapping[str, Any],
    detector_config_path: Path,
    observation_config: Mapping[str, Any],
    sensor_seed: int,
    resume: bool,
) -> Dict[str, np.ndarray]:
    observation_path = sensor_dir / "observations.npz"
    if resume and observation_path.exists():
        return load_npz(observation_path)
    sensor_dir.mkdir(parents=True, exist_ok=True)
    if spec["sweep_type"] == "observation":
        observations = simulate_observation_degradation(
            sequence_dir,
            detector_config_path,
            int(sensor_seed),
            float(spec["axial_observation_keep_probability"]),
            int(observation_config.get("candidate_multiplier", 8)),
        )
    else:
        observations = simulate_sequence_observations(
            sequence_dir,
            detector_config_path,
            sensor_seed=int(sensor_seed),
        )
    save_observations(observations, observation_path)
    return observations


def aggregate_process_targets(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Aggregate repeated process outcomes into one independent sensor row."""

    signed = np.asarray([float(row["final_axis_error_signed"]) for row in rows], dtype=float)
    absolute = np.asarray([float(row["final_axis_error_abs"]) for row in rows], dtype=float)
    squared = np.asarray([float(row["final_axis_error_squared"]) for row in rows], dtype=float)
    axis_rmse = np.asarray([float(row["axis_rmse"]) for row in rows], dtype=float)
    axis_mae = np.asarray([float(row["axis_mae"]) for row in rows], dtype=float)
    if signed.size == 0:
        raise ValueError("At least one process trial is required")
    return {
        "process_trial_count": int(signed.size),
        "mean_final_axis_error_signed": float(np.mean(signed)),
        "variance_final_axis_error": float(np.var(signed, ddof=1)) if signed.size > 1 else 0.0,
        "mean_final_axis_error_squared": float(np.mean(squared)),
        "rmse_final_axis_error": float(np.sqrt(np.mean(squared))),
        "median_final_axis_error_abs": float(np.median(absolute)),
        "q90_final_axis_error_abs": float(np.percentile(absolute, 90.0)),
        "q95_final_axis_error_abs": float(np.percentile(absolute, 95.0)),
        "mean_axis_rmse": float(np.mean(axis_rmse)),
        "variance_axis_rmse": float(np.var(axis_rmse, ddof=1)) if axis_rmse.size > 1 else 0.0,
        "mean_axis_mae": float(np.mean(axis_mae)),
        "failure_probability_005m": float(np.mean(absolute >= 0.05)),
        "failure_probability_010m": float(np.mean(absolute >= 0.10)),
        "failure_probability_020m": float(np.mean(absolute >= 0.20)),
    }


def aggregate_process_trial_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[tuple[str, int], Dict[str, Any]]:
    """Group repeated process trials without treating them as independent scans."""

    grouped: Dict[tuple[str, int], List[Mapping[str, Any]]] = {}
    for row in rows:
        key = (str(row["sequence_id"]), int(row["sensor_seed"]))
        grouped.setdefault(key, []).append(row)
    output: Dict[tuple[str, int], Dict[str, Any]] = {}
    for key, values in grouped.items():
        output[key] = {
            "sequence_id": key[0],
            "sensor_seed": key[1],
            "process_trial_count": len(values),
        }
    return output


def load_yaml(path: Path) -> Dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def load_npz(path: Path) -> Dict[str, np.ndarray]:
    with np.load(path) as loaded:
        return {key: loaded[key].copy() for key in loaded.files}


def read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON mapping in {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> List[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_structured_csv(rows: np.ndarray, path: Path) -> None:
    names = list(rows.dtype.names or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name].item() for name in names})


def relative(root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
