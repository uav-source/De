# Detector Consolidation Stage 2A Gate Report

- Engineering: **ENGINEERING_PASS**
- Geometry Mechanism: **GEOMETRY_MECHANISM_PASS**
- Observation Mechanism: **OBSERVATION_MECHANISM_PASS**
- Detector: **DETECTOR_PASS**
- WEAK_UPDATE_AUTHORIZED: **true**
- RISK_WARNING_AUTHORIZED: **false** (fixed; risk prediction is paused)

## ODI severity detection

- geometry: rho=0.942177, CI=[0.921831, 0.965598], median tau=0.92582, positive ratio=1, paired rate=1.
- observation: rho=0.876331, CI=[0.827411, 0.929852], median tau=0.848668, positive ratio=1, paired rate=0.866667.

## Primary direction

- geometry: alignment median=0.999102, p10=0.981158, stable rate=1, actionable rate=0.998125.
- observation: alignment median=0.999794, p10=0.997688, stable rate=1, actionable rate=1.

Open Control degeneracy false-positive rate: 0.05.
Open Control actionable-direction false-positive rate: 0.05.

Stage 2A does not run toy LIO or process trials, does not predict drift magnitude, does not implement a weak-subspace update, and does not integrate FAST-LIO2.
