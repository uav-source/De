"""Minimum synthetic LIO probe for Day 7."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import numpy as np
import yaml

from .observation_simulator import load_detector_config, load_sequence, quat_to_rot


LEGACY_AXIS_BIAS_BY_FAMILY = {
    "OC": 0.0,
    "CT": 0.016,
    "RT": 0.026,
    "ST": 0.022,
}
LEGACY_NOISE_BY_FAMILY = {
    "OC": {"axis_sigma": 0.003, "cross_sigma": 0.003, "yaw_sigma": 0.0005},
    "CT": {"axis_sigma": 0.004, "cross_sigma": 0.0025, "yaw_sigma": 0.0008},
    "RT": {"axis_sigma": 0.006, "cross_sigma": 0.003, "yaw_sigma": 0.0008},
    "ST": {"axis_sigma": 0.005, "cross_sigma": 0.003, "yaw_sigma": 0.0008},
}
UNBIASED_NOISE_DEFAULT = {
    "axis_sigma": 0.004,
    "cross_sigma": 0.004,
    "yaw_sigma": 0.0008,
}
VALID_AXIS_BIAS_MODES = {"legacy_scene_family", "none", "controlled"}


def run_toy_lio(
    sequence_dir: Union[str, Path],
    config: Union[str, Path, Dict[str, Any]],
    toy_config: Union[None, str, Path, Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sequence_dir = Path(sequence_dir)
    detector_config = load_detector_config(config) if not isinstance(config, dict) else config
    toy_lio_config = load_toy_lio_config(toy_config)
    sequence = load_sequence(sequence_dir)
    observations = np.load(sequence_dir / "observations.npz")

    base_seed = int(toy_lio_config.get("seed", detector_config.get("random_seed", sequence.metadata["random_seed"])))
    seed = base_seed + stable_seed_offset(sequence.sequence_id)
    rng = np.random.default_rng(seed)
    gt = observations["pose_gt"]
    axes = observations["axis_per_frame"]
    packed_J = observations["packed_J"]
    R_diag = observations["R_diag_list"]
    base_residuals = observations["r_list"]
    points_lidar = observations["points_lidar"]
    normals_world = observations["normals_world"]

    est = np.zeros_like(gt)
    est[0] = gt[0]
    family = sequence.metadata["scene_family"]
    applied_axis_bias = []

    for idx in range(1, gt.shape[0]):
        gt_delta = {
            "translation": gt[idx, 1:4] - gt[idx - 1, 1:4],
            "yaw": yaw_from_quat(gt[idx, 4:8]) - yaw_from_quat(gt[idx - 1, 4:8]),
        }
        process_noise = sample_process_noise(family, axes[idx], rng, toy_lio_config)
        applied_axis_bias.append(float(process_noise["axis_bias"]))
        prior = propagate_with_noisy_motion(est[idx - 1], gt_delta, process_noise)
        residual = residual_at_prior(
            prior,
            gt[idx],
            points_lidar[idx],
            normals_world[idx],
            base_residuals[idx],
        )
        est[idx] = lidar_update_pose(prior, packed_J[idx], residual, R_diag[idx])
        est[idx, 0] = gt[idx, 0]

    summary = compute_toy_summary(est, gt, axes)
    bias_metadata = build_bias_metadata(family, toy_lio_config, applied_axis_bias)
    return {
        "poses": est,
        "summary": summary,
        "sequence_id": sequence.sequence_id,
        "random_seed": seed,
        "bias_metadata": bias_metadata,
    }


def propagate_with_noisy_motion(prev_est: np.ndarray, gt_delta: Dict[str, Any], process_noise: Dict[str, Any]) -> np.ndarray:
    prior = prev_est.copy()
    prior[1:4] = prev_est[1:4] + np.asarray(gt_delta["translation"], dtype=float) + np.asarray(process_noise["translation"], dtype=float)
    yaw = yaw_from_quat(prev_est[4:8]) + float(gt_delta["yaw"]) + float(process_noise.get("yaw", 0.0))
    prior[4:8] = yaw_to_quat(yaw)
    return prior


def lidar_update_pose(prior_pose: np.ndarray, J: np.ndarray, r: np.ndarray, R_diag: np.ndarray) -> np.ndarray:
    weighted_J = J / R_diag[:, None]
    H = J.T @ weighted_J
    b = J.T @ (r / R_diag)
    H = 0.5 * (H + H.T)
    damping = max(float(np.max(np.diag(H))) * 1.0e-6, 1.0e-9)
    delta = -np.linalg.solve(H + damping * np.eye(6), b)

    updated = prior_pose.copy()
    updated[1:4] = prior_pose[1:4] + delta[3:6]
    yaw = yaw_from_quat(prior_pose[4:8]) + delta[2]
    updated[4:8] = yaw_to_quat(yaw)
    return updated


def save_pose_est_tum(poses: np.ndarray, output_path: Union[str, Path]) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(
        output_path,
        poses,
        fmt="%.9f %.9f %.9f %.9f %.9f %.9f %.9f %.9f",
    )


def residual_at_prior(
    prior_pose: np.ndarray,
    gt_pose: np.ndarray,
    points_lidar: np.ndarray,
    normals_world: np.ndarray,
    base_residual: np.ndarray,
) -> np.ndarray:
    R_prior = quat_to_rot(prior_pose[4:8])
    R_gt = quat_to_rot(gt_pose[4:8])
    world_prior = (R_prior @ points_lidar.T).T + prior_pose[1:4]
    world_measured = (R_gt @ points_lidar.T).T + gt_pose[1:4]
    geometric = np.einsum("ij,ij->i", normals_world, world_prior - world_measured)
    return geometric + base_residual


def load_toy_lio_config(config: Union[None, str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    if config is None:
        raw: Dict[str, Any] = {}
    elif isinstance(config, dict):
        raw = dict(config)
    else:
        with Path(config).open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        if not isinstance(loaded, dict):
            raise ValueError(f"Toy LIO config must be a mapping: {config}")
        raw = loaded

    mode = str(raw.get("axis_bias_mode", "legacy_scene_family"))
    if mode not in VALID_AXIS_BIAS_MODES:
        raise ValueError(f"Unsupported axis_bias_mode={mode!r}")
    profile = str(raw.get("perturbation_profile", "legacy_day14"))
    normalized = {
        "axis_bias_mode": mode,
        "perturbation_profile": profile,
        "seed": raw.get("seed"),
        "seed_stride": int(raw.get("seed_stride", 1)),
        "n_trials": int(raw.get("n_trials", 1)),
        "controlled_axis_bias": raw.get("controlled_axis_bias", raw.get("axis_bias", None)),
        "noise": raw.get("noise", {}),
        "notes": raw.get("notes", ""),
    }
    if normalized["seed"] is None:
        normalized.pop("seed")
    return normalized


def resolve_process_noise_parameters(family: str, toy_config: Union[None, str, Path, Dict[str, Any]] = None) -> Dict[str, float]:
    config = load_toy_lio_config(toy_config)
    mode = str(config["axis_bias_mode"])
    if mode == "legacy_scene_family":
        noise = dict(LEGACY_NOISE_BY_FAMILY.get(family, LEGACY_NOISE_BY_FAMILY["ST"]))
        axis_bias = float(LEGACY_AXIS_BIAS_BY_FAMILY.get(family, LEGACY_AXIS_BIAS_BY_FAMILY["ST"]))
    else:
        noise_config = config.get("noise", {})
        noise = dict(UNBIASED_NOISE_DEFAULT)
        if isinstance(noise_config, dict):
            for key in ["axis_sigma", "cross_sigma", "yaw_sigma"]:
                if key in noise_config:
                    noise[key] = float(noise_config[key])
        axis_bias = resolve_axis_bias(family, config)
    noise["axis_bias"] = axis_bias
    return noise


def resolve_axis_bias(family: str, toy_config: Union[None, str, Path, Dict[str, Any]] = None) -> float:
    config = load_toy_lio_config(toy_config)
    mode = str(config["axis_bias_mode"])
    if mode == "legacy_scene_family":
        return float(LEGACY_AXIS_BIAS_BY_FAMILY.get(family, LEGACY_AXIS_BIAS_BY_FAMILY["ST"]))
    if mode == "none":
        return 0.0
    controlled = config.get("controlled_axis_bias")
    if isinstance(controlled, dict):
        if family not in controlled:
            raise ValueError(f"controlled_axis_bias must explicitly define family={family!r}")
        return float(controlled[family])
    if controlled is None:
        raise ValueError("axis_bias_mode='controlled' requires controlled_axis_bias")
    return float(controlled)


def sample_process_noise(
    family: str,
    axis: np.ndarray,
    rng: np.random.Generator,
    toy_config: Union[None, str, Path, Dict[str, Any]] = None,
) -> Dict[str, Any]:
    axis = normalize_vector(axis)
    u, v = orthonormal_cross_basis(axis)
    params = resolve_process_noise_parameters(family, toy_config)
    axis_bias = float(params["axis_bias"])
    axis_sigma = float(params["axis_sigma"])
    cross_sigma = float(params["cross_sigma"])
    yaw_sigma = float(params["yaw_sigma"])

    translation = (
        axis * (axis_bias + rng.normal(0.0, axis_sigma))
        + u * rng.normal(0.0, cross_sigma)
        + v * rng.normal(0.0, cross_sigma)
    )
    return {
        "translation": translation,
        "yaw": rng.normal(0.0, yaw_sigma),
        "axis_bias": axis_bias,
        "axis_sigma": axis_sigma,
        "cross_sigma": cross_sigma,
        "yaw_sigma": yaw_sigma,
    }


def build_bias_metadata(family: str, toy_config: Dict[str, Any], applied_axis_bias: list) -> Dict[str, Any]:
    mode = str(toy_config["axis_bias_mode"])
    profile = str(toy_config["perturbation_profile"])
    values = [float(value) for value in applied_axis_bias]
    unique_values = sorted({round(value, 12) for value in values})
    return {
        "scene_family": family,
        "axis_bias_mode": mode,
        "perturbation_profile": profile,
        "legacy_axis_bias": float(LEGACY_AXIS_BIAS_BY_FAMILY.get(family, LEGACY_AXIS_BIAS_BY_FAMILY["ST"])),
        "applied_axis_bias": float(values[0]) if values else resolve_axis_bias(family, toy_config),
        "applied_axis_bias_values": unique_values,
        "is_unbiased_protocol": mode == "none" and all(abs(value) < 1.0e-12 for value in values),
        "bias_source": "scene_family" if mode == "legacy_scene_family" else mode,
    }


def compute_toy_summary(est: np.ndarray, gt: np.ndarray, axes: np.ndarray) -> Dict[str, float]:
    errors = est[:, 1:4] - gt[:, 1:4]
    axis = normalize_rows(axes)
    axis_error = np.abs(np.einsum("ij,ij->i", errors, axis))
    cross_vectors = errors - axis_error[:, None] * axis * np.sign(np.einsum("ij,ij->i", errors, axis))[:, None]
    cross_error = np.linalg.norm(cross_vectors, axis=1)
    final_error = errors[-1]
    return {
        "final_translation_error": float(np.linalg.norm(final_error)),
        "final_axis_error": float(axis_error[-1]),
        "final_cross_error": float(cross_error[-1]),
        "mean_axis_error": float(np.mean(axis_error)),
        "mean_cross_error": float(np.mean(cross_error)),
    }


def write_toy_summary_csv(rows, output_path: Union[str, Path]) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sequence_id",
        "final_translation_error",
        "final_axis_error",
        "final_cross_error",
        "mean_axis_error",
        "mean_cross_error",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for sequence_id, summary in rows:
            row = {"sequence_id": sequence_id}
            row.update(summary)
            writer.writerow(row)


def yaw_from_quat(qxyzw: np.ndarray) -> float:
    x, y, z, w = [float(v) for v in qxyzw]
    return float(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))


def yaw_to_quat(yaw: float) -> np.ndarray:
    half = 0.5 * yaw
    return np.array([0.0, 0.0, np.sin(half), np.cos(half)], dtype=float)


def normalize_vector(values: np.ndarray) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    norm = np.linalg.norm(vector)
    if norm < 1.0e-12:
        raise ValueError("Cannot normalize zero vector")
    return vector / norm


def normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, 1.0e-12)


def orthonormal_cross_basis(axis: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    candidate = np.array([0.0, 0.0, 1.0])
    if abs(float(axis @ candidate)) > 0.9:
        candidate = np.array([1.0, 0.0, 0.0])
    u = normalize_vector(np.cross(axis, candidate))
    v = normalize_vector(np.cross(axis, u))
    return u, v


def stable_seed_offset(sequence_id: str) -> int:
    digest = hashlib.sha256(sequence_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100000
