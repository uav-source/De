# Metric Redesign Stage 1b

## Scope and motivation

Stage 1 completed its engineering pipeline and demonstrated that finite-patch tunnel scenes could produce ordered translation spectra, but its scientific gate was `NO-GO`: none of the candidate metrics reached the pre-registered absolute Spearman threshold with a directional bootstrap interval. More importantly, Stage 1 used `sampling_weight` to create L1-L4, so those levels changed which surfaces were observed more often rather than changing the physical scene. That is an observation intervention, not a defensible real-geometry intervention.

Stage 1b therefore runs two independent experiments. The Geometry Sweep creates one deterministic 16-patch master pool for each geometry seed and selects strength-ranked nested prefixes: L4 is a subset of L3, L3 of L2, and L2 of L1. All shell and patch sampling weights remain 1.0. The Observation Sweep uses the complete, identical scene at O1-O4 and changes only deterministic retention of axial-support candidates. Dropped axial observations are replaced by non-axial candidates so each frame keeps the same point count.

## Paired randomness and statistical unit

The motion surrogate uses common random numbers. A process-noise seed is derived only from `process_seed` and `motion_profile_id`; it excludes sequence ID, level, and sensor seed. Thus paired levels receive byte-identical process increments when their ground-truth trajectory is the same. Ground truth is used by the simulator to create standalone relative-motion measurements and to set the known frame-0 pose. The estimator does not read GT for frame 1 onward propagation or residual construction.

Thirty process trials estimate the conditional error distribution of one sensor run. They do not create 30 independent spectral samples. A `sensor_run_summary.csv` row keyed by sweep, sequence, level, geometry seed, and sensor seed is the independent analysis unit.

## Directional information and cumulative exposure

For the translation Schur information matrix and tunnel-axis unit vector:

\[
I_{\parallel,t}=a_t^T H_{p\mid\theta,t} a_t,\qquad
\bar I_{\parallel,t}=a_t^T \bar H_{p\mid\theta,t}a_t.
\]

The scale-independent directional ratio divides this value by `trace(H)/3 + epsilon`. Stage 1b retains `lambda_min_trans` as a complementary metric because the weakest eigenvector need not be exactly aligned with the known tunnel axis.

The pre-registered primary metric is mean inverse axial information:

\[
E_{\mathrm{inv}}=\sum_t\frac{\Delta t_t}{\bar I_{\parallel,t}+\epsilon},\qquad
\bar E_{\mathrm{inv}}=\frac{E_{\mathrm{inv}}}{\sum_t\Delta t_t}.
\]

The harmonic axial information is the reciprocal counterpart. The analysis also records low-information frame ratio, longest low-information duration, p05/p10/p25 directional information, and weak-subspace persistence using projection matrices rather than sign-ambiguous eigenvectors.

## Pre-registration and hierarchical analysis

Geometry seeds 101, 202, and 303 are train blocks; 404 and 505 are test blocks. The primary metric (`mean_inverse_axis_information`), primary target (`mean_final_axis_error_squared`), directions, thresholds, epsilon, normalization, transform choice, and bootstrap design are written to `preregistered_analysis.json` before data generation. Test data are evaluated once and are never used for automatic parameter selection.

Geometry and Observation Sweeps are reported separately for train and test. Analysis includes paired adjacent-level monotonic rates, per-group Kendall trends, within-level residual Spearman correlations after subtracting train level medians, and 5,000-repetition bootstrap intervals whose outer resampling block is geometry seed.

## Gates

The Engineering Gate checks isolated outputs, expected counts, one-row-per-sensor aggregation, common process noise, and artifact completeness. The Mechanism Gate checks real support ordering and frozen shell/weights for Geometry, and identical geometry plus decreasing realized axial fraction for Observation; at least 80% of paired comparisons must show decreasing axis information. The Prediction Gate uses test seeds only and evaluates the primary metric against the primary target, ODI_trans, the pre-registered rho threshold, directional interval, paired monotonicity, and within-level direction. Only three passing gates produce `STAGE1B_PASS`; a scientific failure remains a normally completed `STAGE1B_NO_GO` run.

## Commands and outputs

```bash
python3 scripts/27_run_metric_redesign_stage1b.py --quick --run-id stage1b_quick_validation
python3 scripts/27_run_metric_redesign_stage1b.py --full --run-id stage1b_full_v1 --workers 8 --resume
python3 scripts/27_run_metric_redesign_stage1b.py --analyze-only \
  --run-dir results/metric_redesign_stage1b/full/stage1b_full_v1
```

Runs are written below `data/metric_redesign_stage1b/<mode>/<run_id>` and `results/metric_redesign_stage1b/<mode>/<run_id>`. Existing run directories are refused unless `--resume` or `--overwrite` is explicit; overwrite removes only that run ID. Tables contain process trials, independent sensor summaries, level summaries, paired trends, separate sweep correlations, within-level residuals, train/test comparison, and gates. Figures show every independent sensor point. Manifests record config hashes, counts, paths, runtime, and gate decisions.

## Limitations and claim boundary

The motion input is a synthetic 6DoF propagation surrogate, not a full IMU. The experiment remains finite-patch synthetic data. Stage 1b does not implement a weak-subspace update, does not integrate FAST-LIO2, does not prove that ODI or the new exposure metric is validated in real LIO, and does not constitute a finished Degen-LIO estimator or paper package.
