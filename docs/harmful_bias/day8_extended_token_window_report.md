# Day 8 Extended Detailed Token Window Report

## Outcome

`DAY8_EXTENDED_TOKEN_WINDOW_EXECUTION_PASS=false`.
`IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED=false`.

## Required answers

1. The prior scan 162 query had no tokens because its frozen detailed window
   was 156--158.
2. The authorized detailed window is 156--163, covering scans 157 and 162
   while remaining inside the unchanged 155--165 summary window.
3. FAST was not changed because the existing binary reads all four window
   bounds from ROS parameters and validates the detailed window is nested.
4. Historical empty-list inference was replaced by
   `TOKEN_CAPTURE_SEMANTICS_V2`.
5. Null-token propagation audit passed:
   `false`.
6. Four fixed replays complete: `true`.
7. Scan 157 full coverage: `true`.
8. Scan 162 full coverage: `true`.
9. First formal query difference: `{"aligned_query_index": 0, "capture_gate_pass": true, "classification": "QUERY_INPUT_DIVERGED", "data_race_proven": false, "day9_authorized": false, "formal_ikdtree_bug_proven": false, "left_query": {"batch_id": "665719930881", "batch_point_index": 0, "candidate_point_sha256": "9b46750a63bd84854d171da8b0c562983ec0ded4a8cfafe2928520e941a0438d", "formal_result_count": 0, "formal_result_members": [], "formal_result_multiset_checksum": 9354609568656401157, "formal_result_ordered_checksum": 14695981039346656037, "formal_result_point_sha256_list": "", "full_cover_subtree_count": 0, "internal_error": 0, "left_child_visit_count": 11, "logical_mutation_epoch": 458, "map_mutation_call_index": 1, "no_intersection_prune_count": 12, "partial_intersection_node_count": 12, "point_deleted_skip_count": 0, "query_box_checksum": 10032829887765577677, "query_box_matches_formal_voxel_contract": 1, "query_box_max_x": 7.5, "query_box_max_y": -8.0, "query_box_max_z": -0.5, "query_box_min_x": 7.0, "query_box_min_y": -8.5, "query_box_min_z": -1.0, "query_sequence": 1, "query_summary_checksum": 11265425160003358114, "rebuild_active": 0, "rebuild_generation": 1, "rebuild_subtree_observed_count": 0, "returned_current_node_point_count": 0, "right_child_visit_count": 12, "run_id": "multihyp_day8_extended_token_r1", "scan_index": 155, "schema_pass": 1, "schema_version": "Day8RangeQuerySummaryV1", "traversal_multiset_checksum": 9354609568656401157, "traversal_ordered_checksum": 14695981039346656037, "tree_deleted_skip_count": 0, "visited_node_count": 24, "voxel_identity": "40e00000c1080000bf80000040f00000c1000000bf000000"}, "left_query_sequence": 1, "left_run_id": "multihyp_day8_extended_token_r1", "left_token_capture_status": "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW", "previous_query_equal": true, "previous_query_index": null, "query_equal": 0, "reason": "strict query identity differs", "right_query": {"batch_id": "665719930881", "batch_point_index": 0, "candidate_point_sha256": "0e68116eed26eb76c6a4fc8798c82ce3d3523c0789578c62a90e228dc066ce51", "formal_result_count": 0, "formal_result_members": [], "formal_result_multiset_checksum": 9354609568656401157, "formal_result_ordered_checksum": 14695981039346656037, "formal_result_point_sha256_list": "", "full_cover_subtree_count": 0, "internal_error": 0, "left_child_visit_count": 11, "logical_mutation_epoch": 458, "map_mutation_call_index": 1, "no_intersection_prune_count": 12, "partial_intersection_node_count": 12, "point_deleted_skip_count": 0, "query_box_checksum": 10032829887765577677, "query_box_matches_formal_voxel_contract": 1, "query_box_max_x": 7.5, "query_box_max_y": -8.0, "query_box_max_z": -0.5, "query_box_min_x": 7.0, "query_box_min_y": -8.5, "query_box_min_z": -1.0, "query_sequence": 1, "query_summary_checksum": 8304463703309259710, "rebuild_active": 0, "rebuild_generation": 1, "rebuild_subtree_observed_count": 0, "returned_current_node_point_count": 0, "right_child_visit_count": 12, "run_id": "multihyp_day8_extended_token_r4", "scan_index": 155, "schema_pass": 1, "schema_version": "Day8RangeQuerySummaryV1", "traversal_multiset_checksum": 9354609568656401157, "traversal_ordered_checksum": 14695981039346656037, "tree_deleted_skip_count": 0, "visited_node_count": 24, "voxel_identity": "40e00000c1080000bf80000040f00000c1000000bf000000"}, "right_query_sequence": 1, "right_run_id": "multihyp_day8_extended_token_r4", "right_token_capture_status": "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW", "root_cause": {"capture_gate_pass": true, "classification": "QUERY_INPUT_DIVERGED", "data_race_proven": false, "day9_authorized": false, "formal_ikdtree_bug_proven": false, "left_token_capture_status": "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW", "reason": "strict query identity differs", "right_token_capture_status": "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW", "root_cause_classification": "EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED", "token_comparison_status": "NOT_APPLICABLE", "token_semantics_version": "TOKEN_CAPTURE_SEMANTICS_V2", "token_sequence_equal": null}, "root_cause_classification": "EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED", "token_comparison_status": "NOT_APPLICABLE", "token_semantics_version": "TOKEN_CAPTURE_SEMANTICS_V2", "token_sequence_equal": null, "traversal_difference": {"capture_gate_pass": true, "classification": "EVIDENCE_GAP", "differing_fields": [], "first_divergent_node_point_sha256": null, "first_divergent_node_range_checksum": null, "first_divergent_query_relation": null, "first_divergent_traversal_token_index": null, "left_token_capture_status": "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW", "right_token_capture_status": "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW", "root_cause_classification": "EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED", "rows": [], "token_comparison_status": "NOT_APPLICABLE", "token_semantics_version": "TOKEN_CAPTURE_SEMANTICS_V2", "token_sequence_equal": null}}`.
10. Previous-query identity complete:
    `true`.
11. Query input and 12. shadow membership are recorded in six-pair evidence.
13. Per-side formal result sets are recorded in the first-query evidence.
14--16. Expected-member visit/deleted/path evidence is in
    `missing_expected_point_witness.json` and the traversal-diff CSV.
17. Rebuild active/generation is preserved per query and token.
18. Formal completeness violation observed: `false`.
19. Range-search context localized: `false`.
20. `FORMAL_IKDTREE_BUG_PROVEN=false`.
21. `DATA_RACE_PROVEN=false`.
22. Read-only instrumentation may perturb timing and scheduling.
23. Day 9 recommended: `false`; scope:
    `None`.
24. `DAY9_AUTHORIZED=false`; a separate GPT audit is required.

Shadow replay is offline-only and never participates in FAST decisions.
Detector, ODI/AIS, weak direction, feedback, GT, commit, push, FAST build, and
FAST tests were not used. Empty or absent token evidence never means equal
traversal under V2.

## Post-lock contract adjudication

The four real replays and their per-run capture gates passed, but the frozen
offline comparison stack did not pass its integration contract:

- r1, r2, and r3 share all 2,413 strict seven-field query identities. Their
  formal result sets and shadow member sets have zero differences.
- r4 shares zero strict seven-field query identities with the other runs; it
  has 2,414 queries versus 2,413. The frozen comparator iterates by positional
  index and therefore reports `QUERY_INPUT_DIVERGED` at index 0 rather than
  producing a strict-identity-aligned formal-result comparison.
- No strict-identity-aligned formal range-query completeness violation was
  reproduced. There is no missing expected-member witness and no explanatory
  traversal-token difference to localize.
- The V2 unit and synthetic tests passed, but the recursive real-output audit
  found 1,728 propagation failures: flattened records retained
  `NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW` while their enclosing query
  classifications were not consistently materialized as `EVIDENCE_GAP`.
- The direct frozen plotter also assumed a `query_box_checksum` column in the
  shadow comparison CSV that is not present. The 15 required plots were
  generated with a plot-only input copy labeled
  `NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED`; original comparison and Gate files
  were not changed.

No analysis source, script, schema, parameter, or Gate was modified after the
runtime lock. These integration failures are preserved as evidence, so
`DAY8_EXTENDED_TOKEN_WINDOW_EXECUTION_PASS=false`,
`DAY8_IKDTREE_RANGE_SEARCH_CONTEXT_PASS=false`, and
`DAY9_RECOMMENDED=false`.
