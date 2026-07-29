from pathlib import Path

from phase_a_v2_active_runner_support import (
    LEGACY_RUNNER_RELATIVE,
    resolve_active_formal_runner,
    unconditional_placeholder_findings,
)


ROOT = Path(__file__).resolve().parents[1]


def test_runner_has_no_unconditional_runtime_error_placeholder():
    binding = resolve_active_formal_runner(ROOT)
    assert binding.active_runner.is_file()
    assert binding.active_runner_relative != LEGACY_RUNNER_RELATIVE
    assert unconditional_placeholder_findings(
        binding.active_runner.read_text(encoding="utf-8")
    ) == []
