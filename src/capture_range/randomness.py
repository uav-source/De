"""Stable method-independent randomness and provenance checksums."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from .types import PerturbationSpec


def _canonical_amplitude(value: float) -> str:
    amplitude = float(value)
    if not math.isfinite(amplitude):
        raise ValueError("signed_amplitude must be finite")
    if amplitude == 0.0:
        amplitude = 0.0
    return amplitude.hex()


def canonical_trial_seed_payload(
    snapshot_id: str,
    perturbation_type: str,
    direction_id: str,
    signed_amplitude: float,
    repeat_index: int,
    global_seed: int,
) -> bytes:
    if not str(snapshot_id) or not str(perturbation_type) or not str(direction_id):
        raise ValueError("seed identity strings must be non-empty")
    if int(repeat_index) < 0 or int(global_seed) < 0:
        raise ValueError("repeat_index and global_seed must be non-negative")
    payload = {
        "direction_id": str(direction_id),
        "global_seed": int(global_seed),
        "perturbation_type": str(perturbation_type),
        "repeat_index": int(repeat_index),
        "signed_amplitude_hex": _canonical_amplitude(signed_amplitude),
        "snapshot_id": str(snapshot_id),
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def derive_trial_seed(
    snapshot_id: str,
    perturbation_type: str,
    direction_id: str,
    signed_amplitude: float,
    repeat_index: int,
    global_seed: int,
) -> int:
    payload = canonical_trial_seed_payload(
        snapshot_id,
        perturbation_type,
        direction_id,
        signed_amplitude,
        repeat_index,
        global_seed,
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def array_checksum(value: Any) -> str:
    array = np.asarray(value)
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(contiguous.dtype.str.encode("ascii"))
    digest.update(json.dumps(list(contiguous.shape), separators=(",", ":")).encode("ascii"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return {
            "array_sha256": array_checksum(value),
            "dtype": value.dtype.str,
            "shape": list(value.shape),
        }
    raise TypeError(f"unsupported checksum value: {type(value).__name__}")


def mapping_checksum(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def perturbation_checksum(perturbation: PerturbationSpec) -> str:
    payload = {
        "direction": np.asarray(perturbation.direction),
        "direction_id": perturbation.direction_id,
        "perturbation_type": perturbation.perturbation_type,
        "repeat_index": perturbation.repeat_index,
        "seed": perturbation.seed,
        "signed_amplitude_hex": _canonical_amplitude(perturbation.signed_amplitude),
        "signed_side": perturbation.signed_side,
    }
    return mapping_checksum(payload)


def noise_checksum(noise: Any) -> str:
    return array_checksum(np.asarray(noise))
