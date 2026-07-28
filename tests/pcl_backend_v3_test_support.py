"""Shared readers for PCL backend qualification v3 tests."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_qualification_v3"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=1)
def protocol_v3():
    return yaml.safe_load(
        (ROOT / "configs/zero_perturbation/backend_qualification_v3.yaml").read_text()
    )


@lru_cache(maxsize=1)
def decision_v3():
    return json.loads((ARTIFACT / "final_decision.json").read_text())
