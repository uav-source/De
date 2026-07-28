"""Frozen namespaced seed schedule for zero-perturbation measurement."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Mapping


NAMESPACE = "zero_perturbation_registration_measurement_v1_20260728"
MODULUS = 2147483647
SPLITS = ("development", "confirmatory")
DOMAINS = ("geometry", "measurement", "bootstrap", "backend")
INDEX_LABELS = {
    "development": {
        "geometry": ((0, "geometry_0"), (1, "geometry_1"), (2, "geometry_2")),
        "measurement": ((0, "measurement_0"), (1, "measurement_1")),
        "bootstrap": ((0, "bootstrap_0"),),
        "backend": ((0, "native"), (1, "open3d")),
    },
    "confirmatory": {
        "geometry": (
            (0, "geometry_0"),
            (1, "geometry_1"),
            (2, "geometry_2"),
            (3, "geometry_3"),
            (4, "geometry_4"),
        ),
        "measurement": (
            (0, "measurement_0"),
            (1, "measurement_1"),
            (2, "measurement_2"),
        ),
        "bootstrap": ((0, "bootstrap_0"),),
        "backend": ((0, "native"), (1, "open3d")),
    },
}


def derive_seed(namespace: str, split: str, domain: str, index: int) -> int:
    """Derive one seed using the frozen SHA-256 algorithm."""

    if namespace != NAMESPACE:
        raise ValueError("namespace is frozen")
    if split not in SPLITS:
        raise ValueError("split must be development or confirmatory")
    if domain not in DOMAINS:
        raise ValueError("invalid seed domain")
    allowed_indices = {item[0] for item in INDEX_LABELS[split][domain]}
    if int(index) not in allowed_indices:
        raise ValueError("index is not frozen for split/domain")
    payload = "{}|{}|{}|{}".format(namespace, split, domain, int(index))
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    seed = int.from_bytes(digest[0:8], byteorder="big", signed=False) % MODULUS
    return 1 if seed == 0 else seed


def seed_records() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for split in SPLITS:
        for domain in DOMAINS:
            for index, label in INDEX_LABELS[split][domain]:
                payload = "{}|{}|{}|{}".format(NAMESPACE, split, domain, index)
                records.append(
                    {
                        "split": split,
                        "domain": domain,
                        "index": index,
                        "label": label,
                        "payload": payload,
                        "seed": derive_seed(NAMESPACE, split, domain, index),
                    }
                )
    return records


def build_seed_schedule(provenance_audit: Mapping[str, Any]) -> Dict[str, Any]:
    records = seed_records()
    values = [int(row["seed"]) for row in records]
    development = {int(row["seed"]) for row in records if row["split"] == "development"}
    confirmatory = {int(row["seed"]) for row in records if row["split"] == "confirmatory"}
    labels: Dict[str, Dict[str, Dict[str, int]]] = {}
    for row in records:
        labels.setdefault(row["split"], {}).setdefault(row["domain"], {})[
            row["label"]
        ] = int(row["seed"])
    duplicate_count = len(values) - len(set(values))
    split_overlap = sorted(development & confirmatory)
    return {
        "schema_version": "zero_perturbation_seed_schedule_v1",
        "namespace": NAMESPACE,
        "algorithm": (
            "seed = int.from_bytes(SHA256(UTF-8(payload))[0:8], "
            "byteorder='big', signed=False) % 2147483647; if seed == 0, seed = 1"
        ),
        "payload_format": "{namespace}|{split}|{domain}|{index}",
        "allowed_splits": list(SPLITS),
        "allowed_domains": list(DOMAINS),
        "labels": labels,
        "records": records,
        "pairwise_duplicate_count": duplicate_count,
        "seed_schedule_pairwise_unique": duplicate_count == 0,
        "development_confirmatory_overlap": split_overlap,
        "development_confirmatory_overlap_count": len(split_overlap),
        "development_confirmatory_seeds_disjoint": not split_overlap,
        "seed_provenance_audit": dict(provenance_audit),
        "derived_seed_provenance_collision": bool(
            provenance_audit.get("derived_seed_provenance_collision", True)
        ),
        "created_before_any_experiment": True,
    }

