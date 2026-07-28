"""Shared readers for the seed-free PCL backend qualification v2 microtests."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests/data/pcl_backend_v2"
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_qualification_v2"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=1)
def protocol_v2():
    return yaml.safe_load(
        (ROOT / "configs/zero_perturbation/backend_qualification_v2.yaml").read_text()
    )


@lru_cache(maxsize=1)
def fixture_manifest():
    return json.loads((DATA / "fixture_manifest.json").read_text())


def read_ascii_xyz_pcd(path: Path) -> np.ndarray:
    lines = path.read_text(encoding="ascii").splitlines()
    data_index = lines.index("DATA ascii") + 1
    return np.asarray(
        [[float(value) for value in line.split()] for line in lines[data_index:] if line],
        dtype=np.float64,
    )
