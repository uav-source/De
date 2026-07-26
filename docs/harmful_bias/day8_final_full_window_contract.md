# Day 8 Final Full-Window Contract

The final Day 8 batch is limited to four new Quick Shack replays. Both the
query-summary and detailed traversal-token windows are scan 155–165. No fifth
replay, FAST source change, FAST build, detector execution, ground-truth use,
or Day 9 self-authorization is permitted.

Queries are aligned only by
`(scan_index, map_mutation_call_index, batch_id, batch_point_index,
candidate_point_sha256, voxel_identity, query_box_checksum)`. Result order and
member multisets are compared separately. Missing token capture is an evidence
gap and never an equal empty trace. Plots consume formal analysis products
through `DAY8_FINAL_PLOT_INPUT_SCHEMA_V1`.

If no strict same-input formal member omission is reproduced in the four runs,
the random real-replay route closes and only a deterministic minimal ikd-tree
fixture with a brute-force oracle is recommended.
