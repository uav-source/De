# Day 8 ikd-tree Range-Search Context Root-Cause Report

## Outcome

`DAY8_EXECUTION_PASS=false`.
The fixed four-run diagnostic localized a first divergent formal range query:
`true`.  The bounded classification set is
`SAME_QUERY_TRACE_DIFFERENT_RESULT`.

## Evidence boundary

The query box comes directly from the existing `Add_Points` downsampling box.
The C++ audit observes the existing `Search_by_range` invocation and result; it
does not add a search or mutate its result.  Detailed traversal tokens cover only
scans 160--163 and contain no node addresses, thread identifiers, coordinates,
or full tree structure.  Offline shadow replay uses only coherent canonical
point identities plus the formal C++ voxel identity.  It never participates in
FAST-LIO2 decisions.

## Required answers

- Four replay runs complete: `true`.
- Query summary counts: `{"multihyp_day8_range_query_r1": 2408, "multihyp_day8_range_query_r2": 2413, "multihyp_day8_range_query_r3": 2413, "multihyp_day8_range_query_r4": 2412}`.
- Traversal token counts: `{"multihyp_day8_range_query_r1": 20807, "multihyp_day8_range_query_r2": 20806, "multihyp_day8_range_query_r3": 20894, "multihyp_day8_range_query_r4": 19954}`.
- Point+voxel snapshots: 22 per run; coherent snapshot Gate:
  `true`.
- First divergent query: `{"aligned_query_index": 637, "classification": "SAME_QUERY_TRACE_DIFFERENT_RESULT", "left_query": {"batch_id": "674309865473", "batch_point_index": 42, "candidate_point_sha256": "050b2143e523351dd7a549f0649ead84f231f02ad28b2962500d5be012f69b12", "formal_result_count": 1, "formal_result_members": ["97b4a58e2f4c2cfa591a7bcad45ea16aaad6dd99e3b27814503fb7a3dc15f72d"], "formal_result_multiset_checksum": 13537233267843924008, "formal_result_ordered_checksum": 7232195853069653836, "formal_result_point_sha256_list": "97b4a58e2f4c2cfa591a7bcad45ea16aaad6dd99e3b27814503fb7a3dc15f72d", "full_cover_subtree_count": 1, "internal_error": 0, "left_child_visit_count": 12, "logical_mutation_epoch": 464, "map_mutation_call_index": 1, "no_intersection_prune_count": 11, "partial_intersection_node_count": 12, "point_deleted_skip_count": 0, "query_box_checksum": 895995171717173285, "query_box_matches_formal_voxel_contract": 1, "query_box_max_x": 3.0, "query_box_max_y": -4.5, "query_box_max_z": -1.0, "query_box_min_x": 2.5, "query_box_min_y": -5.0, "query_box_min_z": -1.5, "query_sequence": 638, "query_summary_checksum": 10145564618059564722, "rebuild_active": 0, "rebuild_generation": 1, "rebuild_subtree_observed_count": 0, "returned_current_node_point_count": 1, "right_child_visit_count": 11, "run_id": "multihyp_day8_range_query_r1", "scan_index": 157, "schema_pass": 1, "schema_version": "Day8RangeQuerySummaryV1", "traversal_multiset_checksum": 9354609568656401157, "traversal_ordered_checksum": 14695981039346656037, "tree_deleted_skip_count": 0, "visited_node_count": 24, "voxel_identity": "40200000c0a00000bfc0000040400000c0900000bf800000"}, "left_query_sequence": 638, "left_run_id": "multihyp_day8_range_query_r1", "previous_query_equal": true, "previous_query_index": 636, "query_equal": 0, "right_query": {"batch_id": "674309865473", "batch_point_index": 42, "candidate_point_sha256": "050b2143e523351dd7a549f0649ead84f231f02ad28b2962500d5be012f69b12", "formal_result_count": 0, "formal_result_members": [], "formal_result_multiset_checksum": 9354609568656401157, "formal_result_ordered_checksum": 14695981039346656037, "formal_result_point_sha256_list": "", "full_cover_subtree_count": 0, "internal_error": 0, "left_child_visit_count": 2, "logical_mutation_epoch": 464, "map_mutation_call_index": 1, "no_intersection_prune_count": 0, "partial_intersection_node_count": 2, "point_deleted_skip_count": 0, "query_box_checksum": 895995171717173285, "query_box_matches_formal_voxel_contract": 1, "query_box_max_x": 3.0, "query_box_max_y": -4.5, "query_box_max_z": -1.0, "query_box_min_x": 2.5, "query_box_min_y": -5.0, "query_box_min_z": -1.5, "query_sequence": 638, "query_summary_checksum": 11939124751291283579, "rebuild_active": 0, "rebuild_generation": 1, "rebuild_subtree_observed_count": 0, "returned_current_node_point_count": 0, "right_child_visit_count": 2, "run_id": "multihyp_day8_range_query_r4", "scan_index": 157, "schema_pass": 1, "schema_version": "Day8RangeQuerySummaryV1", "traversal_multiset_checksum": 9354609568656401157, "traversal_ordered_checksum": 14695981039346656037, "tree_deleted_skip_count": 0, "visited_node_count": 2, "voxel_identity": "40200000c0a00000bfc0000040400000c0900000bf800000"}, "right_query_sequence": 638, "right_run_id": "multihyp_day8_range_query_r4", "root_cause": {"bug_proven": false, "classification": "SAME_QUERY_TRACE_DIFFERENT_RESULT", "classification_schema_pass": true, "day9_authorized": false, "query_completeness_violation_is_diagnostic_not_bug_proof": true, "reason": "recorded query and traversal match but formal result differs"}, "traversal_difference": {"differing_fields": [], "first_differing_token_index": null, "left_token": null, "right_token": null, "token_sequence_equal": true}}`.
- Query boxes, shadow members, formal results, traversal/pruning and deletion/
  rebuild visibility are preserved in the pairwise and first-divergence files.
- Previous query identity complete:
  `true`.
- Formal query completeness violation observed:
  `false`.
- ikd-tree range-search context root cause localized:
  `false`.
- Instrumentation timing perturbation is present and disclosed.
- `FORMAL_IKDTREE_BUG_PROVEN=false`; a diagnostic completeness violation does
  not automatically prove a formal implementation bug.
- `DATA_RACE_PROVEN=false`.
- Stage 3, Stage 4, FAST integration, Patent 2 and Day 9 remain unauthorized.

## Scope

Day 8 diagnoses only range-query and voxel-representative context.  Detector,
ODI/AIS, weak-direction, feedback update, GT, commit and push are all disabled.
