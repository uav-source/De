"""Position-only WGS84 NavSatFix reference and offline trajectory errors."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np


WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
REFERENCE_IS_POSITION_ONLY = True
REFERENCE_ORIENTATION_AVAILABLE = False
ALIGNMENT_METHOD = "rigid_se3_kabsch_no_scale_position_only"


@dataclass(frozen=True)
class NavSatSample:
    timestamp: float
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    status: int
    covariance_x_m2: float = float("nan")
    covariance_y_m2: float = float("nan")
    covariance_z_m2: float = float("nan")

    @property
    def finite(self) -> bool:
        return all(
            math.isfinite(value)
            for value in (
                self.timestamp,
                self.latitude_deg,
                self.longitude_deg,
                self.altitude_m,
            )
        )

    @property
    def rtk_quality(self) -> bool:
        # Lighthouse reports NavSatStatus.GBAS_FIX (2) for its RTK reference.
        return self.finite and self.status >= 2


@dataclass(frozen=True)
class EnuReference:
    timestamps: np.ndarray
    positions_enu_m: np.ndarray
    rtk_quality: np.ndarray
    covariance_diagonal_m2: np.ndarray
    origin: NavSatSample

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "reference_is_position_only": REFERENCE_IS_POSITION_ONLY,
            "reference_orientation_available": REFERENCE_ORIENTATION_AVAILABLE,
            "coordinate_frame": "ENU",
            "origin_rule": "first_valid_rtk_fix",
            "origin_timestamp": self.origin.timestamp,
            "origin_latitude_deg": self.origin.latitude_deg,
            "origin_longitude_deg": self.origin.longitude_deg,
            "origin_altitude_m": self.origin.altitude_m,
            "alignment_method": ALIGNMENT_METHOD,
            "scale_estimated": False,
        }


def geodetic_to_ecef(
    latitude_deg: float, longitude_deg: float, altitude_m: float
) -> np.ndarray:
    latitude = math.radians(float(latitude_deg))
    longitude = math.radians(float(longitude_deg))
    altitude = float(altitude_m)
    sin_lat = math.sin(latitude)
    cos_lat = math.cos(latitude)
    radius = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    return np.asarray(
        [
            (radius + altitude) * cos_lat * math.cos(longitude),
            (radius + altitude) * cos_lat * math.sin(longitude),
            (radius * (1.0 - WGS84_E2) + altitude) * sin_lat,
        ],
        dtype=np.float64,
    )


def ecef_to_enu(
    point_ecef: np.ndarray,
    *,
    origin_ecef: np.ndarray,
    origin_latitude_deg: float,
    origin_longitude_deg: float,
) -> np.ndarray:
    latitude = math.radians(float(origin_latitude_deg))
    longitude = math.radians(float(origin_longitude_deg))
    sin_lat, cos_lat = math.sin(latitude), math.cos(latitude)
    sin_lon, cos_lon = math.sin(longitude), math.cos(longitude)
    rotation = np.asarray(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ],
        dtype=np.float64,
    )
    return rotation @ (
        np.asarray(point_ecef, dtype=np.float64)
        - np.asarray(origin_ecef, dtype=np.float64)
    )


def navsat_to_enu(samples: list[NavSatSample]) -> EnuReference:
    """Use the first finite GBAS/RTK fix as the immutable ENU origin."""

    if not samples:
        raise ValueError("NavSatFix reference is empty")
    ordered = sorted(samples, key=lambda sample: sample.timestamp)
    origins = [sample for sample in ordered if sample.rtk_quality]
    if not origins:
        raise ValueError("no valid RTK fix is available for the ENU origin")
    origin = origins[0]
    usable = [sample for sample in ordered if sample.finite]
    origin_ecef = geodetic_to_ecef(
        origin.latitude_deg, origin.longitude_deg, origin.altitude_m
    )
    positions = np.vstack(
        [
            ecef_to_enu(
                geodetic_to_ecef(
                    sample.latitude_deg,
                    sample.longitude_deg,
                    sample.altitude_m,
                ),
                origin_ecef=origin_ecef,
                origin_latitude_deg=origin.latitude_deg,
                origin_longitude_deg=origin.longitude_deg,
            )
            for sample in usable
        ]
    )
    return EnuReference(
        timestamps=np.asarray([sample.timestamp for sample in usable]),
        positions_enu_m=positions,
        rtk_quality=np.asarray(
            [sample.rtk_quality for sample in usable], dtype=bool
        ),
        covariance_diagonal_m2=np.asarray(
            [
                [
                    sample.covariance_x_m2,
                    sample.covariance_y_m2,
                    sample.covariance_z_m2,
                ]
                for sample in usable
            ],
            dtype=np.float64,
        ),
        origin=origin,
    )


def interpolate_reference(
    reference: EnuReference, timestamps: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    query = np.asarray(timestamps, dtype=np.float64)
    in_range = (query >= reference.timestamps[0]) & (
        query <= reference.timestamps[-1]
    )
    positions = np.full((query.size, 3), np.nan, dtype=np.float64)
    for axis in range(3):
        positions[in_range, axis] = np.interp(
            query[in_range],
            reference.timestamps,
            reference.positions_enu_m[:, axis],
        )
    quality_numeric = np.interp(
        query[in_range],
        reference.timestamps,
        reference.rtk_quality.astype(float),
    )
    quality = np.zeros(query.size, dtype=bool)
    quality[in_range] = quality_numeric >= 1.0 - 1.0e-12
    return positions, quality


def rigid_align_positions(
    estimated_positions: np.ndarray, reference_positions: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit rotation and translation only; metric scale remains fixed at one."""

    estimated = np.asarray(estimated_positions, dtype=np.float64)
    reference = np.asarray(reference_positions, dtype=np.float64)
    if estimated.shape != reference.shape or estimated.ndim != 2 or estimated.shape[1] != 3:
        raise ValueError("estimated/reference positions must share shape N x 3")
    if estimated.shape[0] < 3:
        raise ValueError("at least three positions are required for rigid alignment")
    estimated_center = np.mean(estimated, axis=0)
    reference_center = np.mean(reference, axis=0)
    covariance = (estimated - estimated_center).T @ (
        reference - reference_center
    )
    u, _, vt = np.linalg.svd(covariance)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0.0:
        vt[-1, :] *= -1.0
        rotation = vt.T @ u.T
    translation = reference_center - rotation @ estimated_center
    aligned = estimated @ rotation.T + translation
    return aligned, rotation, translation


def trajectory_error_rows(
    estimator_timestamps: np.ndarray,
    estimator_positions: np.ndarray,
    reference: EnuReference,
    *,
    window_seconds: float = 5.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compute ATE, local translation error, and future error growth offline."""

    timestamps = np.asarray(estimator_timestamps, dtype=np.float64)
    estimated = np.asarray(estimator_positions, dtype=np.float64)
    if timestamps.ndim != 1 or estimated.shape != (timestamps.size, 3):
        raise ValueError("estimator trajectory must be timestamp N and position N x 3")
    reference_positions, rtk_quality = interpolate_reference(reference, timestamps)
    valid = np.all(np.isfinite(reference_positions), axis=1)
    if int(np.sum(valid)) < 3:
        raise ValueError("insufficient estimator/reference temporal overlap")
    aligned_valid, rotation, translation = rigid_align_positions(
        estimated[valid], reference_positions[valid]
    )
    aligned = np.full_like(estimated, np.nan)
    aligned[valid] = aligned_valid
    absolute_error = np.full(timestamps.size, np.nan)
    absolute_error[valid] = np.linalg.norm(
        aligned[valid] - reference_positions[valid], axis=1
    )

    rows: list[dict[str, Any]] = []
    local_errors: list[float] = []
    future_growths: list[float] = []
    for index, timestamp in enumerate(timestamps):
        future_index = int(np.searchsorted(timestamps, timestamp + window_seconds))
        has_window = (
            valid[index]
            and future_index < timestamps.size
            and valid[future_index]
        )
        if has_window:
            estimated_delta = aligned[future_index] - aligned[index]
            reference_delta = (
                reference_positions[future_index] - reference_positions[index]
            )
            local_error = float(np.linalg.norm(estimated_delta - reference_delta))
            future_growth = float(
                absolute_error[future_index] - absolute_error[index]
            )
            local_errors.append(local_error)
            future_growths.append(future_growth)
        else:
            local_error = float("nan")
            future_growth = float("nan")
        rows.append(
            {
                "timestamp": float(timestamp),
                "reference_available": bool(valid[index]),
                "rtk_quality_good": bool(rtk_quality[index]),
                "position_error_m": float(absolute_error[index]),
                "local_translation_error_m": local_error,
                "future_position_error_growth_m": future_growth,
                "future_window_seconds": float(window_seconds),
            }
        )
    metadata = {
        **reference.metadata,
        "position_ate_rmse_m": float(
            np.sqrt(np.mean(np.square(absolute_error[valid])))
        ),
        "position_error_median_m": float(np.median(absolute_error[valid])),
        "local_translation_error_median_m": float(np.median(local_errors)),
        "future_position_error_growth_median_m": float(
            np.median(future_growths)
        ),
        "overlap_count": int(np.sum(valid)),
        "rtk_quality_bad_overlap_count": int(np.sum(valid & ~rtk_quality)),
        "alignment_rotation_row_major": rotation.reshape(-1).tolist(),
        "alignment_translation_m": translation.tolist(),
    }
    return rows, metadata


def weak_direction_angle_error_deg(
    weak_direction: np.ndarray, reference_axis: np.ndarray
) -> float:
    """Compare unoriented axes, eliminating the eigenvector sign ambiguity."""

    weak = np.asarray(weak_direction, dtype=np.float64)
    axis = np.asarray(reference_axis, dtype=np.float64)
    weak_norm, axis_norm = np.linalg.norm(weak), np.linalg.norm(axis)
    if weak.shape != (3,) or axis.shape != (3,) or weak_norm == 0.0 or axis_norm == 0.0:
        raise ValueError("weak direction and reference axis must be nonzero 3-vectors")
    cosine = float(np.clip(abs(np.dot(weak / weak_norm, axis / axis_norm)), 0.0, 1.0))
    return math.degrees(math.acos(cosine))
