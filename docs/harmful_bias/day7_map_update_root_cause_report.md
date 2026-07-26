# Day 7 Map-Update, Rebuild Logger, and ikd-tree Root-Cause Report

`SOURCE_DAY6_INTERNAL_GATE_STATUS=FAIL`

`DAY7_EXTERNAL_ADJUDICATION_APPLIED=true`

`DAY7_EXTERNAL_ADJUDICATION_REASON=OVER_CONSTRAINED_SAME_SCAN_EQUALITY_RULE_FOR_MAP_INSERTION_STAGE`

`DAY7_AUTHORIZED=true`

This report covers only read-only map-update diagnostics in scans 150–170. Point traces contain SHA-256 identities, not coordinates.

## FAST test-fixture remediation

The production FAST build was performed once. Its binary SHA-256 remained `e50f3976522f7c233778947c50610362e277d2946557b8bddf8a98874d1f2aa5`; no production rebuild occurred after either fixture fix.

Two authorized fixture remediations moved three independent 96,000,544-byte test-local `KD_TREE` objects from stack to heap without changing inputs, call order, or assertions. The Day 7 gtest finished with 44/44 passing and the single authorized FAST full-test rerun finished with 356 tests, 0 errors, 0 failures, and 0 skipped.

## Required findings

1. Four replay runs complete: `true`
2. Map insertion divergence reproduced: `true`
3. First divergent scan: `161`
4. First divergent mutation call: `1`
5. First divergent candidate point: `"d54d3ebc609655d3e4b0c9c8a7a7f38e2a530955820bfe52e7b0b008234c2ed2"`
6. First divergent voxel: `"3fc00000c1000000bf00000040000000c0f0000000000000"`
7. Candidate identity equal: `true`
8. Map-before point set equal: `true`
9. Insertion batch equal: `true`
10. Decision context equal: `true`
11. Existing representative run A: `""`
12. Existing representative run B: `""`
13. Selected representative run A: `"d54d3ebc609655d3e4b0c9c8a7a7f38e2a530955820bfe52e7b0b008234c2ed2"`
14. Selected representative run B: `"d54d3ebc609655d3e4b0c9c8a7a7f38e2a530955820bfe52e7b0b008234c2ed2"`
15. Formal outcome run A: `"INSERTED_NEW_VOXEL_REPRESENTATIVE"`
16. Formal outcome run B: `"INSERTED_NEW_VOXEL_REPRESENTATIVE"`
17. Destination run A: `"DIRECT_TREE"`
18. Destination run B: `"DIRECT_TREE"`
19. Rebuild active equal: `true`
20. Rebuild generation equal: `false`
21. Logger append content equal: `true`
22. Logger apply order equal: `true`
23. Logger apply result equal: `true`
24. Map-after only run A: `[]`
25. Map-after only run B: `["0cd97e7c7bda3174869ba79771c7a54885f4c12528dbe62079d050b4a2c1ec98"]`
26. Point difference backlinks complete: `true`
27. Map count delta closed: `true`
28. Root-cause classifications: `["EVIDENCE_GAP"]`
29. Multiple modes: `false`
30. Data race proven: `false`
31. Formal ikd-tree bug proven: `false`
32. Day 8 authorized: `false`

## Gate conclusion

`DAY7_EXECUTION_PASS=true`: all four runs and the evidence-integrity, comparison, immutability, and scope gates completed.

`DAY7_MAP_UPDATE_REBUILD_ROOT_CAUSE_PASS=false`: the scan-161 map-after point difference is captured and backlinked, but the compared formal insertion event is the same on both sides while the prior rebuild generation is already different. With no logger append/apply records in the window, the evidence does not localize the earlier mechanism and remains `EVIDENCE_GAP`.

`DAY8_RECOMMENDED=false`

## Boundaries

`INSTRUMENTATION_TIMING_PERTURBATION_PRESENT=true`. Hashing, buffer writes, and diagnostic atomics may slightly perturb thread timing. A timing association does not prove a data race and does not prove the same behavior in an uninstrumented binary.

No formal map algorithm, Add/Delete decision, rebuild condition, logger order, lock order, OpenMP pragma, or thread configuration was authorized to change. Detector, ODI, weak-direction analysis, and GT were not run.

`DAY8_AUTHORIZED=false`. Any recommendation requires a separate GPT audit. Stage 3 and robust FAST-LIO2 integration remain unauthorized.
