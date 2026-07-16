import hashlib
from pathlib import Path

from eval.stage2_failure_day13_seeds import (
    SEED_MIN,
    SEED_MODULUS,
    generate_seed_namespace,
    seed_candidate,
    seed_label,
)


def test_sha256_seed_formula_and_range_are_exact():
    label = seed_label("calibration", "geometry", 0, 0)
    expected = SEED_MIN + int.from_bytes(hashlib.sha256(label.encode()).digest(), "big") % SEED_MODULUS
    assert seed_candidate(label) == expected
    assert 100000000 <= expected <= 2099999999


def test_namespace_is_deterministic_and_contains_23_unique_values():
    first = generate_seed_namespace({"geometry": [1], "sensor": [2], "process": [3]})
    second = generate_seed_namespace({"process": [3], "sensor": [2], "geometry": [1]})
    assert first == second
    values = [row["seed"] for row in first["records"]]
    assert len(values) == len(set(values)) == 23


def test_seed_implementation_does_not_use_python_hash():
    source = (Path(__file__).resolve().parents[1] / "src/eval/stage2_failure_day13_seeds.py").read_text()
    assert "hash(" not in source
