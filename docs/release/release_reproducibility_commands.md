# Release Reproducibility Commands

Run before packaging:

```bash
python3 scripts/check_env.py
python3 -m pytest -q
STEP_TIMEOUT_SECONDS=120 REPRO_N_BOOT=300 bash scripts/reproduce_day14.sh --run
python3 scripts/08_bias_audit.py
python3 scripts/09_run_unbiased_toy_lio.py --config configs/toy_lio/unbiased_day16.yaml
python3 scripts/10_unbiased_metric_probe.py --config configs/toy_lio/unbiased_day17.yaml
python3 scripts/11_within_sequence_validation.py --config configs/validation/day18_within_sequence.yaml
python3 scripts/12_grouped_loso_validation.py --config configs/validation/day19_grouped_loso.yaml
python3 scripts/13_controlled_partial_validity.py --config configs/validation/day20_controlled_partial.yaml
python3 scripts/14_joint_risk_features.py --config configs/validation/day21_joint_risk.yaml
python3 scripts/15_day22_gate_review.py --config configs/validation/day22_gate_review.yaml
python3 scripts/16_day23_route_b_pivot.py --config configs/validation/day23_route_b_pivot.yaml
python3 scripts/17_day24_diagnostic_consolidation.py --config configs/validation/day24_diagnostic_consolidation.yaml
python3 scripts/18_day25_paper_outline.py --config configs/validation/day25_paper_outline.yaml
python3 scripts/19_day26_paper_skeleton.py --config configs/validation/day26_paper_skeleton.yaml
python3 scripts/20_day27_release_cleanup.py --config configs/validation/day27_release_cleanup.yaml
```

Day 14 reproduction uses smoke plotting and smoke sensitivity for CI stability. Real plot generation should be documented separately when needed.
