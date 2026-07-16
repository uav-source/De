# Stage 2 Day 13 new-seed diagnostic contract

Day 13 is a preregistered diagnostic evaluation of the frozen online statistic
`huber_cusum_max` on a seed namespace that was not used by Day 8–12 or the
historical Stage 2A/2B/2C experiments. It is not a Stage 3 test and it does not
make the final Stage 2 decision.

The design is locked before calibration. Calibration and evaluation use
disjoint SHA-256-derived geometry, sensor, and process seeds, and every new
seed is checked against structured historical seed sources. The only estimator
method is `huber_full`. Geometry L3/L4 and Observation O3/O4 each run clean,
`coherent_subhuber_slip`, and `gross_outlier_control`; Open Control runs clean
only. The stress definitions are read unchanged from the frozen Stage 2C
configuration.

The primary score is the Day 9 `huber_cusum_max` value on rows where
`stat_input_valid`, `window_ready`, and score finiteness all hold. Calibration
uses clean rows only. Its diagnostic operating point is the one-based
nearest-rank 90th percentile and evaluation uses the strict comparison
`score > threshold`. This operating point is only for preliminary clean-FPR
reporting and Day 14 review. It is not a Stage 3 alert threshold and is not used
to decide the Stage 2 Gate.

AUROC uses held-out evaluation rows only, reports Geometry and Observation
separately, handles tied ranks, and bootstraps complete geometry-seed blocks
with 5,000 repetitions and seed 23131. Open Control and gross-outlier control
are excluded from AUROC. Gross control is descriptive evidence about Huber
downweighting. Offline GT metrics are computed only after each online estimator
run and never enter the score, threshold, seed selection, or case selection.

Day 13 success means the locked data and statistical chain is complete. It
authorizes only Day 14 review while retaining `STAGE2_GATE=INCOMPLETE`,
`STAGE3_GATE=NOT_STARTED`, and
`COHERENT_BIAS_DETECTABLE=UNDETERMINED`.
