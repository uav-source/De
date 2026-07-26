# Day 6 Fallback Branch Divergence Root-Cause Audit

Identity: `INTERNAL_ENGINEERING_ROOT_CAUSE_DIAGNOSTICS_ONLY`.

## Authorization lineage

- Pre-permission-normalization SHA: `bf15339f89860438e842b8e37cdfe9ed693fe942e8dac13ed54aa4134413f61f`
- Final-delivery SHA: `a6fad908751adf527812ad2cad5ed497c1f2190dff20f5549e41ef3c36eab61a`
- Change classification: `ARCHIVE_ROOT_PERMISSION_NORMALIZATION`
- `SCIENTIFIC_PAYLOAD_CHANGE_AUTHORIZED=false`

## Answers

1. r1/r2 are semantically identical: `True`.
2. r3 first diverges at record `144`, scan `147`.
3. The previous record is identical: `True`.
4. The first visible objects are valid-count, formal J/h, residual, accepted-index checksum, and formal-correspondence checksum.
5. Prior state does not precede correspondence/measurement divergence; it first differs on the next record.
6. Accepted-index and formal-correspondence checksums first differ at `{'record_index': 144, 'scan_index': 147}` / `{'record_index': 144, 'scan_index': 147}`.
7. J/h/residual first differ at `{'record_index': 144, 'scan_index': 147}` / `{'record_index': 144, 'scan_index': 147}` / `{'record_index': 144, 'scan_index': 147}`.
8. Map size is not recorded, so no map-size onset is observable.
9. No map-content hash is present.
10. No raw sensor payload hash is present.
11. Raw input payload equality is not proven.
12. Map-content equality is not observable.
13. OpenMP data-race causality is not proven.
14. ikd-tree ordering causality is not proven.
15. Post-replay detector nondeterminism is excluded as the generator of the already-frozen FAST branch.
16. Fixed relative-gap distributions are recorded for all runs; r1 median is `0.3788842297869611` and r3 median is `0.37812854499926474`.
17. v1 angle versus gap has descriptive Spearman rho `-0.2125670382731991` with n=`486`; this is not causal proof.
18. Weak-subspace status: `RELATIVELY_MORE_STABLE_BUT_NOT_UNIFORMLY_STABLE`.
19. Cross-run H perturbation is near numerical zero before record 144 and nonzero after the branch.
20. The strongest supported hypothesis is H4: formal correspondence/measurement selection diverges at onset.
21. The largest gaps are raw payload, map-content/order, full correspondence elements, neighbor identity, and scheduling/thread traces.
22. `FAST_BRANCH_ROOT_CAUSE_PROVEN=false` because upstream raw/map/scheduling evidence is missing.
23. The next minimal experiment is bounded input/map-stage digest instrumentation, followed by fine-grained correspondence identity and only then thread sensitivity.
24. `NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED=false`; separate GPT authorization is required.
25. Robust-update integration remains unauthorized because the FAST branch root cause and online stability are not established.

## Bounded conclusions

- Divergence order: `MEASUREMENT_OR_CORRESPONDENCE_DIVERGED_WITH_EQUAL_PRIOR`.
- Near-multiple association: `WEAK_DESCRIPTIVE_ASSOCIATION_NO_EXTREME_NEAR_MULTIPLES`.
- Weak-vector status: `DESCRIPTIVE_LARGE_ANGLE_TAIL_OBSERVED`.
- Audit gate: `True`.
- `FAST_BRANCH_ROOT_CAUSE_PROVEN=false`.
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY6_BRANCH_DIVERGENCE_ROOT_CAUSE`.

Near-multiple eigenspace behavior can help explain weak-vector basis rotation; it does not automatically explain why FAST-LIO2 formal measurements branched.
