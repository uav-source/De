# Day 14 Go/No-Go Report

## Decision

**CONDITIONAL GO**.

This is a GO only for preserving the Day 1-14 synthetic diagnostic package and for continuing with a reduced claim. It is **not** a GO for claiming that ODI robustly predicts drift, and it is not a GO for paper-level main-experiment conclusions.

## Scope Checked

- Current repository HEAD checked with `git rev-parse --short HEAD`.
- `python3 scripts/check_env.py`: OK.
- `python3 -m pytest -q`: `74 passed`.
- Current reproduction manifest checked directly, not assumed from an old run.
- `results/day14/manifests/day14_reproduction_manifest.json`: `status=OK`, `missing_artifacts=[]`, and `git_commit` matched the checked HEAD.
- Reproduction mode: `plot_mode=smoke`, `sensitivity_mode=smoke`.
- `results/day14/figures/plotting_manifest.json`: `smoke_test=true`.

Day 13 intentionally uses smoke plotting and smoke sensitivity in `reproduce_day14.sh --run` for CI stability. Real rendering and real sensitivity are still available outside the mandatory chain:

```bash
python3 scripts/04_plot_day14.py --results results/day14 --out results/day14/figures
python3 scripts/06_sensitivity.py --config configs/detector/odi_default.yaml --results results/day14 --data-root data/minibench --out results/day14/tables --figures-out results/day14/figures --n-boot 300
```

## Gate Evidence

| Gate | Status | Evidence | Interpretation |
|---|---|---|---|
| Engineering reproducibility | PASS | Day 13 manifest `status=OK`, `missing_artifacts=[]`; `pytest=74 passed` | One-command reproduction now completes, with smoke plot/sensitivity for stability. |
| Required artifacts exist | PASS | `day13_reproduction_summary.csv`, raw ODI CSVs, toy TUM files, metrics, tables, figures, manifest | Day 14 package is complete at the artifact level. |
| Weak direction alignment | PASS | ST/CT/RT median axis alignment `1.0`; OC reliable ratio `0.0` | H-derived weak direction aligns with tunnel/local axis in synthetic scenes; OC is not over-interpreted. |
| ODI merged signal | PASS, narrow | ODI vs axis drift merged Spearman `rho=0.647276` | There is an initial merged all-sequence synthetic signal. |
| Per-sequence validity | FAIL | OC `-0.025130`, ST `-0.145586`, CT `0.141986`, RT `-0.288673` | Sequence-internal ODI-axis drift relationship is unstable. |
| LOSO validity | FAIL | Held-out ODI rho: CT `0.141986`, OC `-0.025130`, RT `-0.288673`, ST `-0.145586` | Generalization across held-out sequence families is not stable. |
| Traditional metric competition | CONDITIONAL | AIS `|rho|=0.897659`, lambda_min_clamped `|rho|≈0.697`, ODI `rho=0.647276`, condition_number `rho=0.492916` | ODI beats condition number on merged axis drift but does not beat AIS or lambda_min_clamped. |
| Day 7 toy probe bias | LIMITATION | Day 7 scene-family-dependent axis_bias documented in Day 8/10 reports | Merged correlation may be inflated by synthetic scene family design. |
| Sensitivity | CONDITIONAL | Day 12 real report: merged rho positive across valid D/tau, but per-sequence instability remains; Day 13 current reproduce uses smoke sensitivity | Sensitivity supports the reduced merged-signal claim, not a robust predictor claim. |

## Allowed Claims

- The Day 1-14 minimum synthetic benchmark pipeline is reproducible.
- The 6DoF pose-block information matrix exposes weak directions that align strongly with tunnel/local axes in the synthetic tunnel sequences.
- ODI has a merged-level positive association with axis drift in the current synthetic toy probe.
- ODI is competitive with condition number on the merged axis-drift target.

## Disallowed Claims

- ODI robustly predicts drift.
- ODI is validated by sequence-internal correlation.
- ODI generalizes under leave-one-sequence-out evaluation.
- ODI is clearly superior to AIS or `lambda_min_clamped`.
- The toy LIO drift correlation is paper-main-experiment evidence.

## Final Rationale

The engineering gate is now satisfied: tests pass, artifacts exist, and reproduction completes with a manifest tied to the current commit. The geometry gate is also strong: weak directions are reliable in ST/CT/RT and not forced in OC.

The statistical validity gate is not strong enough for an unconditional GO. Day 10 only supports a merged-level ODI signal, while per-sequence and leave-one-sequence-out checks are unstable or negative. AIS and `lambda_min_clamped` remain strong competing indicators, and the Day 7 toy probe has a scene-family-dependent axis-bias confound.

Therefore the final Day 14 judgment is **CONDITIONAL GO**: continue only with reduced claims and explicit bias warnings.
