# Degen-LIO Diagnostic Benchmark

This repository is a diagnostic benchmark / failure-analysis package for LiDAR-Inertial degeneracy.
It is not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized by the current evidence chain.
ODI robust drift prediction is not validated.

## Project Scope

This workspace preserves the Day 14-Day 30 evidence chain for a synthetic diagnostic benchmark. The project studies how degeneracy metrics, weak-direction diagnostics, toy probes, and gate reviews behave under increasingly strict validation.

The current route is Route B: diagnostic benchmark / failure-analysis. It is not a method implementation route.

## Metric Redesign Stage 1

The incremental Stage 1 workflow replaces infinite tunnel planes with finite patches, separates geometry/sensor/process randomness, removes estimator ground-truth leakage, and evaluates translation-marginal spectra on independent sensor runs. See [docs/metric_redesign_stage1.md](docs/metric_redesign_stage1.md). This workflow does not authorize a weak-subspace update or validate a complete Degen-LIO method.

## Metric Redesign Stage 1b

Stage 1b separates real geometry removal from fixed-geometry observation loss, adds directional and cumulative weak-constraint exposure metrics, pairs process noise across levels, and evaluates train/test results with geometry-block statistics. See [docs/metric_redesign_stage1b.md](docs/metric_redesign_stage1b.md). Quick and full runs are isolated by mode and run ID; Stage 1 outputs are not overwritten.

```bash
python3 scripts/27_run_metric_redesign_stage1b.py --quick --run-id stage1b_quick_validation
python3 scripts/27_run_metric_redesign_stage1b.py --full --run-id stage1b_full_v1 --workers 8 --resume
```

## What This Repository Does

- Builds a reproducible synthetic minibench for open-control and tunnel-like degeneracy cases.
- Computes whitened information metrics, weak-direction alignment, ODI, AIS, lambda_min_clamped, and condition_number diagnostics.
- Audits the legacy toy_lio scene-family axis-bias confound.
- Establishes an unbiased synthetic toy probe protocol.
- Runs within-sequence, grouped / LOSO, controlled partial, and joint-risk validity screens.
- Records go/no-go gates, claim boundaries, paper-outline artifacts, and release hygiene plans.

The central diagnostic question is:

> Can a reproducible diagnostic benchmark expose when degeneracy metrics and risk features fail under stricter validation?

## What This Repository Does Not Claim

- It does not provide a validated Degen-LIO estimator method.
- It does not authorize weak-subspace update implementation.
- It does not claim toy_lio is real LIO.
- It does not claim ODI is superior to AIS, lambda_min_clamped, or condition_number.
- It does not claim joint risk features are validated drift predictors.

## Evidence Chain Day14-Day30

- Day 14: conditional go/no-go report for the initial synthetic probe.
- Day 15: legacy toy_lio scene-family axis-bias audit.
- Day 16: unbiased toy_lio protocol with zero applied axis bias.
- Day 17: unbiased multi-trial synthetic probe.
- Day 18: window-level within-sequence validation.
- Day 19: grouped / LOSO metric validation.
- Day 20: controlled / partial validity analysis.
- Day 21: joint risk feature screening.
- Day 22: formal gate review with `NO_GO_METHOD_UPDATE`.
- Day 23: Route B pivot to diagnostic benchmark / metric redesign.
- Day 24: diagnostic benchmark consolidation.
- Day 25: paper outline and figure/table plan.
- Day 26: paper skeleton and release cleanup plan.
- Day 27: README scope update, release hygiene audit, and figure/table readiness review.
- Day 28: paper-draft table conversion and pending figure planning.
- Day 29: real F01/F03 figure generation and table interpretation safeguards.
- Day 30: final package review, artifact audit, claim-boundary audit, and release readiness check.

## Reproduction Commands

Run these commands from the repository root:

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
python3 scripts/21_day28_figure_table_generation.py --config configs/validation/day28_figure_table_generation.yaml
python3 scripts/22_day29_safe_figures.py --config configs/validation/day29_safe_figures.yaml
python3 scripts/23_day30_final_package_review.py --config configs/validation/day30_final_package_review.yaml
```

## Smoke vs Real Plotting

The Day 14 one-command reproduction uses smoke plotting and smoke sensitivity modes for CI stability. Smoke mode verifies file structure, manifests, and table availability. Real plotting remains available through the plotting scripts, but should be run separately and documented as a real-render pass.

## Release Package Contents

The release package should include source code, configs, scripts, tests, docs, reports, selected `results/day30/tables`, selected `results/day30/manifests`, and required Day 14 manifests.

The release archive must exclude `.git`, `.pytest_cache`, `__pycache__`, matplotlib/font caches, and other local cache artifacts. Raw trajectory files should either be regenerated by scripts or explicitly documented if packaged.

## Known Limitations

- The benchmark is synthetic-only.
- toy_lio is a synthetic probe, not real LIO.
- ODI and joint risk features did not pass the strict controlled/gated validation chain.
- The scene-family count is small.
- The project does not include an authorized estimator update.
- Smoke plotting differs from real rendering.

## Forbidden Claims

The following claims are forbidden under the current evidence chain:

- ODI robust drift prediction is validated.
- ODI superiority over AIS/lambda_min is not established.
- Degen-LIO estimator-method validation is not established.
- Weak-subspace update authorization is absent.
- toy_lio results are real LIO results.
