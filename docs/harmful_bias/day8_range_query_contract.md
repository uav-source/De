# Day 8 ikd-tree Range-Query Diagnostic Contract

## Authorization and scope

Day 8 is limited to
`IKDTREE_RANGE_SEARCH_AND_VOXEL_REPRESENTATIVE_CONTEXT_DIAGNOSTICS`.
It observes the production `KD_TREE::Add_Points` downsample range query,
its unchanged formal result, and bounded state already visited by the existing
recursive `Search_by_range`. It does not authorize Stage 3, Stage 4,
FAST-LIO2 integration, Patent 2, or Day 9.

The fixed replay window is scans 155 through 165, inclusive. Detailed traversal
tokens are limited to scans 160 through 163. Exactly four sequential Quick
Shack replays are authorized, on ROS master ports 20511--20514, with FAST on CPU
22, rosbag on CPU 23, and playback rate 0.25.

## Formal-semantics boundary

The query box is the pre-existing `Add_Points` voxel box:

`min = floor(point / downsample_size) * downsample_size`

`max = min + downsample_size`

All lower bounds are inclusive and all upper bounds are exclusive. The audit
must not modify this formula, the existing query call, no-intersection/full-cover
predicates, current-left-right visitation order, deleted-flag logic, flatten
order, locks, rebuild reader protocol, representative selection, logger logic,
or map mutation. It must not add range/nearest searches or diagnostic tree
traversals.

## Bounded evidence

Per run, buffers are preallocated and bounded:

- query summaries: 65,536;
- detailed traversal tokens: 1,048,576;
- formal result members: 262,144;
- coherent point+voxel snapshots: 22;
- point+voxel pairs: 262,144.

Overflow increments a diagnostic counter and stops further diagnostic capture;
it cannot overwrite prior evidence, block FAST, or change a formal result. All
overflow and schema error counts must be zero.

The hot path may copy formal local scalars, calculate canonical identities, and
append to its fixed single-producer buffers. It may not perform file I/O,
CSV/JSON formatting, sorting, Python execution, sleeps, large dynamic
allocation, console flooding, or new map/search traversal. Export is allowed
only after safe shutdown/drain.

No node/root/rebuild addresses, thread identifiers, full coordinates, full map,
point cloud, or full tree structure are captured.

`INSTRUMENTATION_TIMING_PERTURBATION_PRESENT=true` is mandatory.

## Offline shadow replay

The offline shadow state starts from each coherent `MAP_BEFORE` snapshot's
canonical `(point_sha256, formal_voxel_identity)` pairs. It replays Day 7
mutation events in formal order and must close exactly to the coherent
`MAP_AFTER` identity set. Before each production range query it compares the
logical members of the queried formal voxel with the unchanged production
result.

The formal voxel identity is emitted by the C++ implementation using the exact
production voxel formula. Python only decodes that identity; it does not invent
a second voxel rule. Shadow replay never participates in FAST-LIO2 decisions.

## Classification and claim boundary

Every pairwise first difference must use one fixed classification:

- `QUERY_INPUT_DIVERGED`;
- `SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED`;
- `DELETION_FLAG_VISIBILITY_DIVERGED`;
- `REBUILD_SUBTREE_VISIBILITY_DIVERGED`;
- `TREE_TRAVERSAL_PRUNING_DIVERGED`;
- `FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP`;
- `TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE`;
- `SAME_QUERY_TRACE_DIFFERENT_RESULT`;
- `NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED`;
- `EVIDENCE_GAP`.

A formal-result/shadow-membership mismatch is diagnostic evidence, not automatic
proof of an ikd-tree bug or data race. Day 8 fixes
`FORMAL_IKDTREE_BUG_PROVEN=false`, `DATA_RACE_PROVEN=false`, and
`DAY9_AUTHORIZED=false`.
