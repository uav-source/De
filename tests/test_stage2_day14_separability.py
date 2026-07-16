from eval.stage2_day14_decision import evaluate_separability
from eval.stage2_day14_schema import GateStatus


def test_low_matched_clean_fpr_cannot_override_failed_auroc():
    result = evaluate_separability(
        geometry_auroc=0.5993,
        observation_auroc=0.6862,
        weak_clean_fpr=0.10017857142857142,
        matched_clean_fprs=(0.091875, 0.07875),
        auroc_min=0.80,
        clean_fpr_max=0.10,
    )
    assert result.status == GateStatus.FAIL
    assert "cannot substitute" in result.reason


def test_lenient_interpretation_still_requires_one_auroc_at_target():
    result = evaluate_separability(0.79, 0.79, 0.05, (0.05, 0.05), 0.80, 0.10)
    assert result.status == GateStatus.FAIL

