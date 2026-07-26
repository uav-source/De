# Day 8 Final Full-Window Reproduction Report

This was the authorized final random real-replay batch: exactly four new Quick Shack runs were executed and no fifth replay was added.

## Fixed scope

- Query-summary window: scan 155–165.
- Detailed traversal-token window: scan 155–165, chosen to cover every formal query in the summary window.
- FAST source modified: false; FAST rebuilt or tested: false.
- Strict identity: `(scan_index, map_mutation_call_index, batch_id, batch_point_index, candidate_point_sha256, voxel_identity, query_box_checksum)`.
- Comparison is identity-keyed. Positional query comparison is not used.
- Result order differences are reported separately and never treated as member omissions.
- Null-token semantics are fully propagated; absent capture is never treated as an equal empty trace.
- Plotter inputs are the formal comparison, root-cause, coverage, accounting, cost, and route-decision outputs only.

## Replay and comparison outcome

- Four runs complete: `true`.
- Full-window token coverage: `true`.
- Strict same-input formal member divergence reproduced: `true`.
- Formal completeness violation observed: `true`.
- Root cause: `TREE_TRAVERSAL_PRUNING_DIVERGED`.
- Root-cause localized: `true`.
- Pair summaries: `[{"aligned_prefix_length": 888, "common_identity_count": 888, "first_identity_stream_divergence": {"left_identity": {"batch_id": "678604832769", "batch_point_index": 0, "candidate_point_sha256": "553e756ca862d115517a43f9b05b976b43c39f49b1ff6a4425a8d05541ecc58e", "map_mutation_call_index": 1, "query_box_checksum": 14905750648924745037, "scan_index": 158, "voxel_identity": "40c00000c1180000bfc0000040d00000c1100000bf800000"}, "right_identity": {"batch_id": "678604832769", "batch_point_index": 0, "candidate_point_sha256": "fc830d6368962fbb6663bd21412c2182a50f6ce5924c7457a4dc3f18e39e4c8a", "map_mutation_call_index": 1, "query_box_checksum": 14905750648924745037, "scan_index": 158, "voxel_identity": "40c00000c1180000bfc0000040d00000c1100000bf800000"}, "stream_index": 888}, "formal_result_order_only_divergence_count": 1, "identity_stream_classification": "QUERY_STREAM_IDENTITY_DIVERGED", "left_identity_count": 2401, "left_only_identity_count": 1513, "left_run_id": "multihyp_day8_final_full_window_r1", "right_identity_count": 2413, "right_only_identity_count": 1525, "right_run_id": "multihyp_day8_final_full_window_r2", "root_cause_classification": "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP", "strict_identity_formal_member_set_divergence_count": 1}, {"aligned_prefix_length": 888, "common_identity_count": 888, "first_identity_stream_divergence": {"left_identity": {"batch_id": "678604832769", "batch_point_index": 0, "candidate_point_sha256": "553e756ca862d115517a43f9b05b976b43c39f49b1ff6a4425a8d05541ecc58e", "map_mutation_call_index": 1, "query_box_checksum": 14905750648924745037, "scan_index": 158, "voxel_identity": "40c00000c1180000bfc0000040d00000c1100000bf800000"}, "right_identity": {"batch_id": "678604832769", "batch_point_index": 0, "candidate_point_sha256": "fc830d6368962fbb6663bd21412c2182a50f6ce5924c7457a4dc3f18e39e4c8a", "map_mutation_call_index": 1, "query_box_checksum": 14905750648924745037, "scan_index": 158, "voxel_identity": "40c00000c1180000bfc0000040d00000c1100000bf800000"}, "stream_index": 888}, "formal_result_order_only_divergence_count": 1, "identity_stream_classification": "QUERY_STREAM_IDENTITY_DIVERGED", "left_identity_count": 2401, "left_only_identity_count": 1513, "left_run_id": "multihyp_day8_final_full_window_r1", "right_identity_count": 2413, "right_only_identity_count": 1525, "right_run_id": "multihyp_day8_final_full_window_r3", "root_cause_classification": "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP", "strict_identity_formal_member_set_divergence_count": 1}, {"aligned_prefix_length": 888, "common_identity_count": 888, "first_identity_stream_divergence": {"left_identity": {"batch_id": "678604832769", "batch_point_index": 0, "candidate_point_sha256": "553e756ca862d115517a43f9b05b976b43c39f49b1ff6a4425a8d05541ecc58e", "map_mutation_call_index": 1, "query_box_checksum": 14905750648924745037, "scan_index": 158, "voxel_identity": "40c00000c1180000bfc0000040d00000c1100000bf800000"}, "right_identity": {"batch_id": "678604832769", "batch_point_index": 0, "candidate_point_sha256": "fc830d6368962fbb6663bd21412c2182a50f6ce5924c7457a4dc3f18e39e4c8a", "map_mutation_call_index": 1, "query_box_checksum": 14905750648924745037, "scan_index": 158, "voxel_identity": "40c00000c1180000bfc0000040d00000c1100000bf800000"}, "stream_index": 888}, "formal_result_order_only_divergence_count": 1, "identity_stream_classification": "QUERY_STREAM_IDENTITY_DIVERGED", "left_identity_count": 2401, "left_only_identity_count": 1513, "left_run_id": "multihyp_day8_final_full_window_r1", "right_identity_count": 2413, "right_only_identity_count": 1525, "right_run_id": "multihyp_day8_final_full_window_r4", "root_cause_classification": "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP", "strict_identity_formal_member_set_divergence_count": 1}, {"aligned_prefix_length": 2413, "common_identity_count": 2413, "first_identity_stream_divergence": null, "formal_result_order_only_divergence_count": 12, "identity_stream_classification": "STRICT_QUERY_IDENTITY_STREAM_EQUAL", "left_identity_count": 2413, "left_only_identity_count": 0, "left_run_id": "multihyp_day8_final_full_window_r2", "right_identity_count": 2413, "right_only_identity_count": 0, "right_run_id": "multihyp_day8_final_full_window_r3", "root_cause_classification": "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED", "strict_identity_formal_member_set_divergence_count": 0}, {"aligned_prefix_length": 2413, "common_identity_count": 2413, "first_identity_stream_divergence": null, "formal_result_order_only_divergence_count": 3, "identity_stream_classification": "STRICT_QUERY_IDENTITY_STREAM_EQUAL", "left_identity_count": 2413, "left_only_identity_count": 0, "left_run_id": "multihyp_day8_final_full_window_r2", "right_identity_count": 2413, "right_only_identity_count": 0, "right_run_id": "multihyp_day8_final_full_window_r4", "root_cause_classification": "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED", "strict_identity_formal_member_set_divergence_count": 0}, {"aligned_prefix_length": 2413, "common_identity_count": 2413, "first_identity_stream_divergence": null, "formal_result_order_only_divergence_count": 15, "identity_stream_classification": "STRICT_QUERY_IDENTITY_STREAM_EQUAL", "left_identity_count": 2413, "left_only_identity_count": 0, "left_run_id": "multihyp_day8_final_full_window_r3", "right_identity_count": 2413, "right_only_identity_count": 0, "right_run_id": "multihyp_day8_final_full_window_r4", "root_cause_classification": "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED", "strict_identity_formal_member_set_divergence_count": 0}]`.

## Claim boundary and route decision

- Shadow replay is offline evidence and never participates in FAST decisions.
- Instrumentation can perturb scheduling and timing.
- A query anomaly would not automatically prove a production bug or data race.
- `FORMAL_IKDTREE_BUG_PROVEN=false`; `DATA_RACE_PROVEN=false`.
- Random replay route: `COMPLETED_WITH_LOCALIZED_QUERY_PATH_WITNESS`.
- Further random replay authorized: `false`.
- Deterministic minimal fixture recommended: `false`.
- Next scope: `MINIMAL_IKDTREE_PRUNING_ISOLATION`.
- Day 9 remains unauthorized and requires independent GPT audit.
- The evidence does not authorize Stage 3 or a FAST robust-update path.

## Scientific state

- `STAGE2_GATE=FAIL`; `TRANSITION=PIVOT`.
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`.
- Detector and ground truth were not used.
