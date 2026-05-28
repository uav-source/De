# Day 15-30 Scope Freeze

Day 14 ended with **CONDITIONAL GO**, not an unconditional GO. Day 15-30 is therefore a bias-removal and validation phase, not a paper-packaging phase and not a full Degen-LIO method-development phase.

## Primary Objectives

1. Fix the scene-family-dependent `axis_bias` exposed in the legacy Day 7 `toy_lio` probe.
2. Build an unbiased toy probe where perturbations are independent of scene family, expected degeneracy, ODI, AIS, and lambda metrics.
3. Recompute trajectory metrics from saved trajectories, GT, axis files, and ODI/AIS/lambda tables.
4. Validate metrics within each sequence, not only after merging all windows across scene families.
5. Compare ODI fairly against AIS, `lambda_min_clamped`, and `condition_number`.
6. Permit a weak-subspace update prototype only after unbiased validation passes.

## Non-Negotiable Limits

- Day 14 remains **CONDITIONAL GO**.
- Legacy biased `toy_lio` is diagnostic evidence only.
- Day 10 per-sequence and LOSO counter-evidence must remain visible.
- AIS and `lambda_min_clamped` remain strong competing metrics until a fair comparison says otherwise.
- Synthetic toy-probe results must not be described as real LIO or real SLAM results.
- The project must not claim that ODI is a robust drift predictor based on Day 14.

## Required Gates Before Weak-Subspace Update

Weak-subspace update work is blocked until all of the following are available:

1. A bias audit proving the legacy axis-bias confound is frozen and not reused as main evidence.
2. An unbiased perturbation protocol with equal perturbation statistics across OC/ST/CT/RT.
3. Unbiased toy-probe trajectories for all four sequences and all required perturbation seeds.
4. Window-level metrics for axis drift, cross drift, and weak-direction drift.
5. Metric validity tables reporting merged, per-sequence, per-perturbation, and LOSO results.
6. A clear answer on whether ODI adds value beyond AIS, `lambda_min_clamped`, and `condition_number`.

## Day 15-30 Decision Discipline

Day 30 must choose exactly one:

- **GO**: proceed to real LIO baseline integration only if unbiased validation, within-sequence evidence, update baselines, and robustness gates all pass.
- **CONDITIONAL GO**: continue prototype work with reduced claims and explicit limitations.
- **NO-GO**: demote ODI to an auxiliary degeneracy descriptor if the unbiased evidence does not support it.

The expected default remains **CONDITIONAL GO** unless unbiased evidence becomes substantially stronger.
