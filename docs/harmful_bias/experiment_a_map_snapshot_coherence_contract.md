# Experiment A Map Snapshot Coherence Contract

This internal engineering diagnostic replaces the revoked unlocked map
snapshot from the preceding Experiment A audit.

- Snapshot schema: `coherent_map_snapshot_v2`
- Stage schema: `experiment_a_stage_hash_record_v2`
- Snapshot method:
  `KD_TREE_REBUILD_PTR_THEN_WORKING_MUTEX_COPY_V1`
- Window: scans 135 through 160 inclusive
- Required evidence: two runs, 26 stage records per run, 52 coherent map
  snapshots per run, 104 total
- Accepted snapshot status: `COHERENT_SYNCHRONIZED_COPY`
- Required continuity: zero within-run cross-scan violations

The content digest is an order-independent multiset reduction over canonical
point hashes. The traversal digest is an order-sensitive fold over the coherent
copy order. Equal content with different traversal records tree/storage order,
not a logical-map content difference. These finite checksums have a theoretical
collision limitation and are engineering identity evidence, not mathematical
proof.

Classification is closed as
`EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT` unless every required snapshot and
continuity invariant passes. No detector, ODI, weak-direction metric, GT,
development split, holdout split, or future-test split is part of this task.
Day 7 remains unauthorized regardless of the diagnostic result.

