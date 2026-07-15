# Stage 2 Day 11B deterministic replay contract

Day 11B replays only the two cases preregistered by the immutable Day 11A lock.
They are mechanism-oriented deterministic diagnostic cases, not historical
representative seeds and not an independent Test. They cannot select a
threshold or decide the Stage 2 gate.

The matrix is exactly two sweeps (`geometry`, `observation`) by the historical
Test pair (`clean`, `coherent_subhuber_slip`) by the two formal methods
(`huber_full`, `huber_projected_gain`), for eight method replays. The frozen
Stage 2C control stress `gross_outlier_control` is not replayed. No stress-name
alias is permitted. The earlier Stage 2B stress name is not a Stage 2C replay
name.

`coherent_subhuber_slip` is the frozen Stage 2C sustained coherent bias below
the Huber threshold. Both methods share the same immutable scene, observation,
stress, process-noise, initial-state, and covariance inputs. Each method is run
with logging disabled and enabled; estimator arrays and discrete outputs must
remain exactly checksum-equivalent.

Online estimation receives a guarded mapping with all ground-truth fields
hidden. Offline GT evaluation runs only after estimation. Day 9 window records
consume only Day 8 online records. Stress traces reuse the frozen residual,
variance, and Huber implementation and never feed back into estimation.

The merged CSV is only a Day 12 diagnostic visualization input. Day 11B creates
no figures, alerts, thresholds, classification metrics, detection delay,
Stage 3 work, or FAST-LIO2 integration. Stage 2 remains incomplete.
