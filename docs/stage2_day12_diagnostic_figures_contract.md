# Stage 2 Day 12 diagnostic-figure contract

Day 12 has one input: the provenance-complete frozen Day 11B v2 replay. Day 11B v1 is provenance-incomplete and cannot supply plotting data. The input audit recomputes file hashes, method identity, row keys, base-observation pairing, axial-only contamination, and the two saved stress bursts before any figure is created.

The four preregistered figures show: weak-direction innovation and frozen-window mean timelines; prior/posterior absolute axial error; current same-sign run length; and clean/coherent box-plus-all-frame descriptive distributions. Stress shading comes only from saved `stress_active` rows. There is no added smoothing, interpolation, forward filling, clipping, or case selection.

The Geometry and Observation cases are deterministic diagnostic cases, not representative seeds and not an independent Test. Same-sign runs have no cutoff. Frame-wise scatter and box summaries contain serially correlated descriptive data and are not inferential samples. No significance test, best statistic, best method, online cutoff, AUROC, or FPR is produced. These figures neither support nor reject H2.

Day 13, if authorized by the Day 12 reproducibility gate, must use wholly new seeds and must not mix the Day 11 cases into its evaluation. Stage 2 remains incomplete, Stage 3 has not started, FAST-LIO2 is not integrated, and this repository is not a complete Degen-LIO system.
