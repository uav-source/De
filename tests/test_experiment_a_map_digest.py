from __future__ import annotations

from fastlio2_adapter.experiment_a_stage_hash import map_digest


P1 = (1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0)
P2 = (5.0, 6.0, 7.0, 8.0, 0.0, 0.0, 0.0, 0.0)


def test_map_content_digest_is_order_independent() -> None:
    first = map_digest([P1, P2])
    second = map_digest([P2, P1])
    assert (
        first["map_content_multiset_checksum"]
        == second["map_content_multiset_checksum"]
    )


def test_map_traversal_digest_is_order_sensitive() -> None:
    first = map_digest([P1, P2])
    second = map_digest([P2, P1])
    assert (
        first["map_traversal_order_checksum"]
        != second["map_traversal_order_checksum"]
    )
