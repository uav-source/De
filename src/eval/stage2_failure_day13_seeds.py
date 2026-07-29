"""Deterministic new-seed namespace and historical exclusion audit for Day 13."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableSet, Optional, Sequence, Tuple

from eval.analysis_lock import sha256_file
from eval.synthetic_pipeline_common import load_yaml, write_json


SEED_NAMESPACE = "Degen-LIO-Day13-v1"
SEED_MIN = 100_000_000
SEED_MODULUS = 2_000_000_000
SEED_TYPES = ("geometry", "sensor", "process")
SEED_ROLES = ("calibration", "evaluation")
SEED_COUNTS = {
    "calibration": {"geometry": 5, "sensor": 2, "process": 2},
    "evaluation": {"geometry": 10, "sensor": 2, "process": 2},
}
HISTORICAL_SCAN_ROOTS = (
    "artifacts/current",
    "artifacts/history",
    "configs/update",
    "results/stage2_failure_analysis",
)
STRUCTURED_SUFFIXES = {".json", ".yaml", ".yml", ".csv"}
SEED_TYPE_ALIASES = {
    "geometry": "geometry",
    "measurement": "sensor",
    "sensor": "sensor",
    "process": "process",
}
SEED_KEY_PATTERN = re.compile(
    r"(?:^|_)(geometry|measurement|sensor|process)_seeds?(?:_value)?$"
)
STRUCTURED_SEED_KEYS = frozenset({"index", "label", "value", "values"})


def seed_label(role: str, seed_type: str, index: int, nonce: int) -> str:
    """Return the exact preregistered SHA-256 label for one seed candidate."""

    _validate_role_type(role, seed_type)
    if int(index) < 0 or int(nonce) < 0:
        raise ValueError("seed index and nonce must be non-negative")
    return (
        f"{SEED_NAMESPACE}|role={role}|type={seed_type}|"
        f"index={int(index)}|nonce={int(nonce)}"
    )


def seed_candidate(label: str) -> int:
    """Map a complete label to the frozen integer interval without randomness."""

    digest = hashlib.sha256(str(label).encode("utf-8")).digest()
    return SEED_MIN + int.from_bytes(digest, byteorder="big", signed=False) % SEED_MODULUS


def generate_seed(
    role: str,
    seed_type: str,
    index: int,
    excluded: Iterable[int],
    used: MutableSet[int],
) -> Tuple[int, int, str]:
    """Generate one seed, incrementing nonce only to avoid locked exclusions."""

    _validate_role_type(role, seed_type)
    forbidden = {int(value) for value in excluded}
    nonce = 0
    while True:
        label = seed_label(role, seed_type, int(index), nonce)
        value = seed_candidate(label)
        if value not in forbidden and value not in used:
            used.add(value)
            return value, nonce, label
        nonce += 1


def generate_seed_namespace(
    historical_seeds: Mapping[str, Iterable[int]],
) -> Mapping[str, Any]:
    """Generate all 23 Day 13 seeds in a stable role/type/index order."""

    normalized = {
        seed_type: sorted({int(value) for value in historical_seeds.get(seed_type, [])})
        for seed_type in SEED_TYPES
    }
    used: MutableSet[int] = set()
    roles: Dict[str, Dict[str, list]] = {}
    records = []
    for role in SEED_ROLES:
        roles[role] = {}
        for seed_type in SEED_TYPES:
            values = []
            for index in range(SEED_COUNTS[role][seed_type]):
                value, nonce, label = generate_seed(
                    role, seed_type, index, normalized[seed_type], used
                )
                values.append(value)
                records.append({
                    "role": role,
                    "seed_type": seed_type,
                    "index": index,
                    "nonce": nonce,
                    "label": label,
                    "seed": value,
                })
            roles[role][seed_type] = values
    calibration = {
        value for values in roles["calibration"].values() for value in values
    }
    evaluation = {
        value for values in roles["evaluation"].values() for value in values
    }
    all_values = [int(row["seed"]) for row in records]
    historical_union = {value for values in normalized.values() for value in values}
    return {
        "namespace": SEED_NAMESPACE,
        "algorithm": (
            "100000000 + int.from_bytes(SHA256(label), byteorder='big', "
            "signed=False) mod 2000000000; nonce increments on collision"
        ),
        "roles": roles,
        "records": records,
        "historical_overlap_count": len(set(all_values) & historical_union),
        "calibration_evaluation_overlap_count": len(calibration & evaluation),
        "new_internal_duplicate_count": len(all_values) - len(set(all_values)),
    }


def scan_historical_seed_sources(root: Path) -> Mapping[str, Any]:
    """Parse every structured Stage 2 source that declares typed seeds."""

    root = Path(root).resolve()
    candidates = []
    for relative in HISTORICAL_SCAN_ROOTS:
        directory = root / relative
        if not directory.is_dir():
            continue
        candidates.extend(
            path for path in directory.rglob("*")
            if path.is_file()
            and path.suffix.lower() in STRUCTURED_SUFFIXES
            and "stage2_day13_diagnostic" not in path.parts
            and "day13_new_seed" not in path.parts
        )
    sources = []
    hashes: Dict[str, str] = {}
    found = {seed_type: set() for seed_type in SEED_TYPES}
    provenance = []
    parse_errors = []
    for path in sorted(set(candidates), key=lambda value: str(value.relative_to(root))):
        raw = path.read_text(encoding="utf-8", errors="strict")
        lowered = raw.lower()
        if not any(f"{seed_type}_seed" in lowered for seed_type in SEED_TYPES):
            continue
        relative = str(path.relative_to(root))
        sources.append(relative)
        hashes[relative] = sha256_file(path)
        try:
            records = _extract_path_seed_records(path, relative)
            for record in records:
                found[record["seed_type"]].add(record["seed_value"])
            provenance.extend(records)
        except (ValueError, TypeError, json.JSONDecodeError, UnicodeError) as error:
            parse_errors.append({"path": relative, "error": str(error)})
    if not sources:
        parse_errors.append({"path": "<scan>", "error": "no historical seed sources found"})
    return {
        "schema_version": "stage2_failure_day13_seed_exclusion_v1",
        "scan_roots": list(HISTORICAL_SCAN_ROOTS),
        "source_paths": sources,
        "source_sha256": hashes,
        "historical_geometry_seeds": sorted(found["geometry"]),
        "historical_sensor_seeds": sorted(found["sensor"]),
        "historical_process_seeds": sorted(found["process"]),
        "historical_seed_provenance": _deduplicate_provenance(provenance),
        "parse_errors": parse_errors,
        "historical_source_parse_pass": not parse_errors,
    }


def build_seed_exclusion_manifest(root: Path) -> Mapping[str, Any]:
    """Scan history, generate Day 13 seeds, and record all disjointness checks."""

    scan = dict(scan_historical_seed_sources(root))
    historical = {
        seed_type: scan[f"historical_{seed_type}_seeds"] for seed_type in SEED_TYPES
    }
    generated = generate_seed_namespace(historical)
    roles = generated["roles"]
    manifest = {
        **scan,
        "seed_generation_namespace": SEED_NAMESPACE,
        "seed_generation_algorithm": generated["algorithm"],
        "new_calibration_geometry_seeds": roles["calibration"]["geometry"],
        "new_calibration_sensor_seeds": roles["calibration"]["sensor"],
        "new_calibration_process_seeds": roles["calibration"]["process"],
        "new_evaluation_geometry_seeds": roles["evaluation"]["geometry"],
        "new_evaluation_sensor_seeds": roles["evaluation"]["sensor"],
        "new_evaluation_process_seeds": roles["evaluation"]["process"],
        "seed_records": generated["records"],
        "historical_overlap_count": generated["historical_overlap_count"],
        "calibration_evaluation_overlap_count": generated[
            "calibration_evaluation_overlap_count"
        ],
        "new_internal_duplicate_count": generated["new_internal_duplicate_count"],
    }
    manifest["audit_pass"] = bool(
        manifest["historical_source_parse_pass"]
        and manifest["historical_overlap_count"] == 0
        and manifest["calibration_evaluation_overlap_count"] == 0
        and manifest["new_internal_duplicate_count"] == 0
    )
    return manifest


def validate_seed_exclusion_manifest(manifest: Mapping[str, Any]) -> None:
    """Recompute all new seeds and reject edited source hashes or seed lists."""

    if manifest.get("schema_version") != "stage2_failure_day13_seed_exclusion_v1":
        raise ValueError("unexpected Day 13 seed exclusion schema")
    if manifest.get("seed_generation_namespace") != SEED_NAMESPACE:
        raise ValueError("Day 13 seed namespace changed")
    historical = {
        seed_type: [int(value) for value in manifest[f"historical_{seed_type}_seeds"]]
        for seed_type in SEED_TYPES
    }
    generated = generate_seed_namespace(historical)
    for role in SEED_ROLES:
        for seed_type in SEED_TYPES:
            field = f"new_{role}_{seed_type}_seeds"
            if list(manifest.get(field, [])) != generated["roles"][role][seed_type]:
                raise ValueError(f"Day 13 generated seed list changed: {field}")
    for field in (
        "historical_overlap_count",
        "calibration_evaluation_overlap_count",
        "new_internal_duplicate_count",
    ):
        if int(manifest.get(field, -1)) != int(generated[field]):
            raise ValueError(f"Day 13 seed audit count changed: {field}")
    expected_pass = bool(
        manifest.get("historical_source_parse_pass")
        and not generated["historical_overlap_count"]
        and not generated["calibration_evaluation_overlap_count"]
        and not generated["new_internal_duplicate_count"]
    )
    if bool(manifest.get("audit_pass")) != expected_pass or not expected_pass:
        raise ValueError("Day 13 seed exclusion audit did not pass")


def write_seed_exclusion_manifest(root: Path, path: Path) -> Mapping[str, Any]:
    manifest = build_seed_exclusion_manifest(root)
    validate_seed_exclusion_manifest(manifest)
    write_json(path, manifest)
    return manifest


def extract_seed_values_with_provenance(
    value: Any,
    json_path: str,
    *,
    source_file: str = "<memory>",
    seed_type: Optional[str] = None,
    declared_seed_type: Optional[str] = None,
    container_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Strictly extract integers from one explicit seed-bearing context."""

    inferred = _seed_key_types(json_path.rsplit(".", 1)[-1])
    canonical_type = seed_type or (inferred[0] if inferred else None)
    declared_type = declared_seed_type or (inferred[1] if inferred else None)
    if canonical_type not in SEED_TYPES or declared_type not in SEED_TYPE_ALIASES:
        raise ValueError(f"unsupported seed-bearing JSON path: {json_path}")

    def extract(item: Any, path: str, context: str) -> list[dict[str, Any]]:
        if type(item) is int:
            return [{
                "seed_value": item,
                "source_file": source_file,
                "json_path": path,
                "container_type": context,
                "seed_type": canonical_type,
                "declared_seed_type": declared_type,
            }]
        if isinstance(item, bool):
            raise ValueError(f"boolean is not a seed at {path}")
        if isinstance(item, float):
            raise ValueError(f"float is not a seed at {path}: {item!r}")
        if isinstance(item, str):
            raise ValueError(f"string is not a seed at {path}: {item!r}")
        if isinstance(item, (list, tuple)):
            if not item:
                raise ValueError(f"empty seed list at {path}")
            records = []
            for index, child in enumerate(item):
                records.extend(extract(child, f"{path}[{index}]", "list"))
            return records
        if isinstance(item, Mapping):
            keys = {str(key) for key in item}
            unknown = sorted(keys - STRUCTURED_SEED_KEYS)
            if unknown:
                child = _json_child_path(path, unknown[0])
                raise ValueError(f"unrecognized seed container leaf at {child}")
            if "value" in item and "values" in item:
                raise ValueError(f"ambiguous structured seed container at {path}")
            if "value" not in item and "values" not in item:
                raise ValueError(f"structured seed container has no value at {path}")
            if "index" in item and type(item["index"]) is not int:
                raise ValueError(f"invalid seed metadata at {_json_child_path(path, 'index')}")
            if "label" in item and not isinstance(item["label"], str):
                raise ValueError(f"invalid seed metadata at {_json_child_path(path, 'label')}")
            key = "value" if "value" in item else "values"
            child = item[key]
            if key == "values" and not isinstance(child, (list, tuple)):
                raise ValueError(
                    f"structured seed values must be a list at "
                    f"{_json_child_path(path, key)}"
                )
            return extract(
                child,
                _json_child_path(path, key),
                f"structured_{key}",
            )
        raise ValueError(f"unsupported seed value at {path}: {type(item).__name__}")

    return extract(value, json_path, container_type or "scalar")


def extract_typed_seed_provenance(
    value: Any, *, source_file: str = "<memory>"
) -> list[dict[str, Any]]:
    """Walk a document, entering strict parsing only at typed seed keys."""

    records: list[dict[str, Any]] = []

    def walk(item: Any, json_path: str) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                key_text = str(key)
                child_path = _json_child_path(json_path, key_text)
                types = _seed_key_types(key_text)
                if types is None:
                    walk(child, child_path)
                    continue
                canonical_type, declared_type = types
                records.extend(extract_seed_values_with_provenance(
                    child,
                    child_path,
                    source_file=source_file,
                    seed_type=canonical_type,
                    declared_seed_type=declared_type,
                ))
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                walk(child, f"{json_path}[{index}]")

    walk(value, "$")
    return _deduplicate_provenance(records)


def _extract_path_seed_records(path: Path, source_file: Optional[str] = None) -> list[dict[str, Any]]:
    source = source_file or str(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        records = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("CSV has no header")
            for row_index, row in enumerate(reader):
                for key, value in row.items():
                    types = _seed_key_types(key)
                    if types is None or not str(value).strip():
                        continue
                    text = str(value).strip()
                    json_path = _json_child_path(f"$[{row_index}]", str(key))
                    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", text) is None:
                        raise ValueError(f"CSV seed cell is not a canonical integer at {json_path}")
                    canonical_type, declared_type = types
                    records.extend(extract_seed_values_with_provenance(
                        int(text),
                        json_path,
                        source_file=source,
                        seed_type=canonical_type,
                        declared_seed_type=declared_type,
                        container_type="csv_integer_cell",
                    ))
        return _deduplicate_provenance(records)
    value = json.loads(path.read_text(encoding="utf-8")) if suffix == ".json" else load_yaml(path)
    return extract_typed_seed_provenance(value, source_file=source)


def _extract_path_seeds(path: Path) -> Mapping[str, set]:
    output = {seed_type: set() for seed_type in SEED_TYPES}
    for record in _extract_path_seed_records(path):
        output[record["seed_type"]].add(record["seed_value"])
    return output


def _deduplicate_provenance(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique = {}
    for record in records:
        row = dict(record)
        key = (
            str(row["source_file"]),
            str(row["json_path"]),
            str(row["seed_type"]),
            int(row["seed_value"]),
        )
        unique[key] = row
    return [unique[key] for key in sorted(unique)]


def _json_child_path(parent: str, key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return f"{parent}.{key}"
    return f"{parent}[{json.dumps(key, ensure_ascii=False)}]"


def _seed_key_types(key: Any) -> Optional[tuple[str, str]]:
    match = SEED_KEY_PATTERN.search(str(key).lower())
    if match is None:
        return None
    declared = match.group(1)
    return SEED_TYPE_ALIASES[declared], declared


def _typed_seed_key(key: Any) -> Optional[str]:
    types = _seed_key_types(key)
    return types[0] if types else None


def _seed_integer(value: Any, key: str) -> int:
    if type(value) is int:
        return value
    if isinstance(value, bool):
        raise ValueError(f"boolean is not a seed: {key}")
    raise ValueError(f"non-integer seed in {key}: {value!r}")


def _validate_role_type(role: str, seed_type: str) -> None:
    if role not in SEED_ROLES or seed_type not in SEED_TYPES:
        raise ValueError(f"unsupported Day 13 seed role/type: {role}/{seed_type}")
