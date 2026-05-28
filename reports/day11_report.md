# Day 11 Report - Diagnostic Visualization

## Completed Items

- Implemented `scripts/04_plot_day14.py`.
- Added `tests/test_plot_day14.py`.
- Generated all required diagnostic figures as both PNG and PDF.
- Generated `results/day14/figures/plotting_manifest.json`.

## Reproducibility Record

- Date: 2026-05-28
- Repository: `/home/lj/Degen-LIO`
- Base git commit at run start: `b33b960`
- Detector config: `configs/detector/odi_default.yaml`
- Random seed: `42`
- Plot command: `python3 scripts/04_plot_day14.py --results results/day14 --out results/day14/figures`

## Run Commands

```bash
python3 scripts/check_env.py
python3 -m pytest -q
python3 scripts/00_generate_minibench.py --all
python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml
python3 scripts/03_eval_metrics.py --all --config configs/detector/odi_default.yaml
python3 scripts/05_metric_validity.py --config configs/detector/odi_default.yaml
python3 scripts/04_plot_day14.py --results results/day14 --out results/day14/figures
```

## Verification

- `python3 scripts/check_env.py`: OK
- `python3 -m pytest -q`: `71 passed in 6.22s`

## Output Files

- `results/day14/figures/Fig_D14_01_spectrum_across_scenes.png`
- `results/day14/figures/Fig_D14_01_spectrum_across_scenes.pdf`
- `results/day14/figures/Fig_D14_02_odi_timeline.png`
- `results/day14/figures/Fig_D14_02_odi_timeline.pdf`
- `results/day14/figures/Fig_D14_03_alignment_hist.png`
- `results/day14/figures/Fig_D14_03_alignment_hist.pdf`
- `results/day14/figures/Fig_D14_04_odi_vs_axis_drift_merged_and_per_sequence.png`
- `results/day14/figures/Fig_D14_04_odi_vs_axis_drift_merged_and_per_sequence.pdf`
- `results/day14/figures/Fig_D14_05_metric_validity_comparison.png`
- `results/day14/figures/Fig_D14_05_metric_validity_comparison.pdf`
- `results/day14/figures/Fig_D14_06_axis_cross_error.png`
- `results/day14/figures/Fig_D14_06_axis_cross_error.pdf`
- `results/day14/figures/Fig_D14_07_bias_audit_summary.png`
- `results/day14/figures/Fig_D14_07_bias_audit_summary.pdf`
- `results/day14/figures/plotting_manifest.json`

## Figure Diagnostics

### Fig_D14_01_spectrum_across_scenes

1. This figure asks whether the whitened information spectrum is more concentrated in tunnel-like scenes than in OC.
2. It supports the degeneracy setup because ST/CT/RT have near-null trailing eigenvalues while OC keeps a broader normalized spectrum.
3. It limits the claim because spectrum concentration alone does not prove drift prediction, and Day 10 shows AIS and `lambda_min_clamped` are strong competing spectrum summaries.

### Fig_D14_02_odi_timeline

1. This figure asks whether ODI, AIS, and `lambda_min_clamped` exist as framewise online signals rather than only post-hoc sequence labels.
2. It supports the detector pipeline because all four sequences export continuous time-series values from per-frame `H_tilde`.
3. It limits the claim because a clean detector timeline does not imply robust per-sequence drift prediction.

### Fig_D14_03_alignment_hist

1. This figure asks whether reliable weak directions align with the tunnel or local axis.
2. It supports the Day 9 result because ST/CT/RT reliable frames concentrate near axis alignment `1.0`, while OC has no reliable weak-direction frames.
3. It limits the claim because OC cannot be interpreted through forced weak directions, and reliability filtering is essential to avoid false explanations.

### Fig_D14_04_odi_vs_axis_drift_merged_and_per_sequence

1. This figure asks whether the merged ODI-axis drift signal survives when split by sequence.
2. It supports only the merged positive signal, matching Day 10 merged ODI vs axis drift Spearman rho `0.647276`.
3. It limits the claim because the per-sequence panels show unstable sequence-internal relationships, so the merged plot must not be reported alone.

### Fig_D14_05_metric_validity_comparison

1. This figure asks whether ODI is uniquely strong compared with `condition_number`, `lambda_min_clamped`, and AIS.
2. It supports ODI only partially because ODI beats `condition_number` in merged axis-drift Spearman magnitude and high-drift AUC.
3. It limits the claim because AIS and `lambda_min_clamped` are stronger merged Spearman competitors, and LOSO held-out points are unstable.

### Fig_D14_06_axis_cross_error

1. This figure asks whether toy-probe drift is directional rather than just larger ATE.
2. It supports the synthetic tunnel probe because ST/CT/RT axis errors are much larger than cross errors, while OC remains small.
3. It limits the claim because the Day 7 scene-family-dependent `axis_bias` contributes to these differences and prevents direct paper-level validity claims.

### Fig_D14_07_bias_audit_summary

1. This figure asks whether the Day 10 scientific warning is visible rather than hidden behind a positive merged scatter.
2. It supports the cautious interpretation by showing the merged ODI signal alongside per-sequence instability, LOSO instability, and axis-bias risk.
3. It limits the claim explicitly: Day 10 only supports merged-level ODI signal, not robust sequence-internal drift prediction.

## Scientific Conclusion

Day 10 only supports merged-level ODI signal, not robust sequence-internal drift prediction.
Do not write "ODI robustly predicts drift" based on the current toy probe.
The current diagnostic figures are suitable for Day 14 gate discussion, not for paper main-experiment claims.

## Failed Items

- None in script execution.
- Scientific limitation remains: per-sequence and leave-one-sequence-out evidence are unstable.

## Day 12 Most Important Task

- Implement sensitivity checks for whitening scale, `tau_w`, and reliability thresholds.
- Keep all diagnostic plots and reports separated into merged, per-sequence, and LOSO evidence.
