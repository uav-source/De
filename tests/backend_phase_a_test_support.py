"""Shared readers for the Phase A protocol-lock tests."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from zero_perturbation.backend_phase_a_protocol import (
    load_backend_phase_a_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_phase_a_lock"


@lru_cache(maxsize=1)
def protocol():
    return load_backend_phase_a_protocol(ROOT)


def artifact_json(name: str):
    return json.loads((ARTIFACT / name).read_text(encoding="utf-8"))
