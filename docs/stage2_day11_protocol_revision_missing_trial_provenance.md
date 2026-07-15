# Day 11 protocol revision: missing Stage 2C trial provenance

The frozen 36,000-trial Stage 2C Reserved Test completed successfully, but its
`method_trial_summary.csv`, `paired_method_differences.csv`, and generated data
directory were not retained. The compact aggregate artifact is not sufficient
to recover trial keys, per-trial metrics, or input checksums.

Historical Stage 2C trial-level outputs were not retained.

No trial-level results were reconstructed or inferred.

The recovery audit searched `/home/lj`, `/mnt`, `/media`, `/tmp`, Git history
and unreachable objects, the desktop trash, and historical archives. It found
no copy of either target CSV. Consequently, the previous historical
representative-seed replay protocol is withdrawn. Day 11 now preregisters two
deterministic diagnostic cases using only frozen Test seed lists and a fixed
SHA-256 modulo rule. Selection does not use performance, innovation, CUSUM,
ground-truth error, solver status, plot visibility, randomness, or a manual
override.

The stress provenance has three distinct layers:

- The Stage 2C stress config and update lock allow `clean`,
  `coherent_subhuber_slip`, and `gross_outlier_control`.
- The frozen historical Stage 2C Test executed only `clean` and
  `coherent_subhuber_slip`.
- Day 11B is locked to that same two-regime historical Test subset.

`coherent_subhuber_slip` is the frozen Stage 2C sustained, coherent bias stress
whose injected slip remains below the Huber threshold. The name
`axial_correspondence_slip` belongs to the earlier Stage 2B historical
experiment and is not a frozen Stage 2C stress name. No alias is used.
`gross_outlier_control` remains an allowed Stage 2C control stress, but it was
not part of the historical Test clean/coherent replay pair and is therefore not
replayed by Day 11B.

The selected cases are mechanism-oriented examples, not historical
representative statistics and not a new independent Test. They cannot be used
to select thresholds, authorize alerts, or decide the Stage 2 Gate. Any Day 12
figures may be described only as diagnostic case visualizations. The planned
Day 13 new-seed, multi-case experiment must supply the primary statistical
evidence.

Stage 2 remains incomplete, Stage 3 has not started, FAST-LIO2 is not
integrated, and the repository is not a complete Degen-LIO system.
