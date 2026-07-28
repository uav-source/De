"""Shared readers for stopped backend-qualification contract tests."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_qualification"


@lru_cache(maxsize=1)
def qualification_protocol():
    return yaml.safe_load(
        (ROOT / "configs/zero_perturbation/backend_qualification_v1.yaml").read_text(
            encoding="utf-8"
        )
    )


@lru_cache(maxsize=1)
def qualification_decision():
    return json.loads((ARTIFACT / "final_decision.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def qualification_manifest():
    return json.loads((ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))

