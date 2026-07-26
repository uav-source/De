from pathlib import Path

import pytest

import capture_range.day2_development_protocol as development_protocol
from capture_range.day2_development_protocol import (
    DEVELOPMENT_YAML_RELATIVE,
    DEVELOPMENT_YAML_SHA256,
    PARENT_FILE_HASHES,
    file_sha256,
    load_day2_development_protocol,
)


ROOT = Path(__file__).resolve().parents[1]


def test_development_yaml_and_archived_parents_are_byte_exact():
    assert file_sha256(ROOT / DEVELOPMENT_YAML_RELATIVE) == DEVELOPMENT_YAML_SHA256
    assert {
        path: file_sha256(ROOT / path) for path in PARENT_FILE_HASHES
    } == dict(PARENT_FILE_HASHES)


def test_loader_parses_only_the_independent_development_yaml(monkeypatch):
    loaded_paths = []
    original = development_protocol._load_unique_yaml

    def recording_loader(path):
        loaded_paths.append(path.relative_to(ROOT))
        return original(path)

    monkeypatch.setattr(development_protocol, "_load_unique_yaml", recording_loader)
    protocol = load_day2_development_protocol(ROOT)

    assert loaded_paths == [DEVELOPMENT_YAML_RELATIVE]
    assert protocol.section("protocol")["protocol_type"] == "exploratory_development"
    assert protocol.section("protocol")["confirmatory_test_seed_access"] == "forbidden"
    with pytest.raises(TypeError):
        protocol.data["protocol"] = {}


def test_unique_key_loader_rejects_silently_shadowed_yaml(tmp_path):
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text("root:\n  key: first\n  key: second\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid Day 2 Development YAML"):
        development_protocol._load_unique_yaml(duplicate)
