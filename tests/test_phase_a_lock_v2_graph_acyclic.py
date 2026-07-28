from zero_perturbation.phase_a_lock_architecture_v2 import lock_dependency_graph


def test_layer_graph_is_acyclic_without_duplicate_edges() -> None:
    graph = lock_dependency_graph()
    assert graph["LOCK_GRAPH_ACYCLIC"] is True
    assert graph["LOCK_GRAPH_DUPLICATE_BINDING_COUNT"] == 0
    assert len(graph["edges"]) == 3

