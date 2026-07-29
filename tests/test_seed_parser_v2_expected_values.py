import json
from pathlib import Path

from eval.stage2_failure_day13_seeds import extract_typed_seed_provenance


ROOT = Path(__file__).resolve().parents[1]
SCIENTIFIC_LOCK = ROOT / (
    "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/"
    "phase_a_scientific_protocol_lock_v2.json"
)


def test_seed_parser_extracts_all_frozen_v2_values_exactly() -> None:
    records = extract_typed_seed_provenance(
        json.loads(SCIENTIFIC_LOCK.read_text(encoding="utf-8")),
        source_file=str(SCIENTIFIC_LOCK.relative_to(ROOT)),
    )
    geometry = [row["seed_value"] for row in records if row["declared_seed_type"] == "geometry"]
    measurement = [row["seed_value"] for row in records if row["declared_seed_type"] == "measurement"]
    assert geometry == [1850310744, 1957656152, 1334931069]
    assert measurement == [217775206, 1664898153]
    assert {row["seed_type"] for row in records if row["declared_seed_type"] == "measurement"} == {"sensor"}
