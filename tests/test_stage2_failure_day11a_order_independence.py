from eval.stage2_failure_deterministic_case import build_candidate_pool, select_case


def test_input_order_cannot_change_pool_or_selected_case():
    first = build_candidate_pool(
        "geometry", ["L4", "L3"], [20, 10], [2, 1], [101, 100]
    )
    second = build_candidate_pool(
        "geometry", ["L3", "L4"], [10, 20], [1, 2], [100, 101]
    )
    assert first == second
    first_digest, first_index, first_selected = select_case(first, "fixed-label")
    second_digest, second_index, second_selected = select_case(second, "fixed-label")
    assert (first_digest, first_index, first_selected) == (
        second_digest,
        second_index,
        second_selected,
    )
