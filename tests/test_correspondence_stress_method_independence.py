from pathlib import Path


def test_stress_seed_source_has_no_method_or_process_seed_dependency():
    source = (Path(__file__).parents[1] / "src/minibench/correspondence_stress.py").read_text(encoding="utf-8")
    signature = source[source.index("def _digest"):]
    assert "method" not in signature
    assert "process_seed" not in signature
