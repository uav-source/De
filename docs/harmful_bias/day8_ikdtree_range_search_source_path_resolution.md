# Day 8 ikd-tree Range-Search Source-Path Resolution

## Resolution status

`DAY8_SOURCE_PATH_RESOLUTION_PASS=true`

The resolution below was completed before any Day 8 source modification.
Every required path is `CONFIRMED`.

## Formal downsample query

- source_file: `include/ikd-Tree/ikd_Tree.cpp`
- symbol: `KD_TREE<PointType>::Add_Points`
- line_range: 719–970
- source_sha256:
  `52166cb088f5efb9546bc82ecf09b1940118163039e0af8979d9b62c5c9ace78`
- formal_input: each `PointToAdd[i]` when
  `downsample_on && DOWNSAMPLE_SWITCH`
- formal_output: the existing `Downsample_Storage` returned by the single
  formal `Search_by_range` call at line 801
- query_box_source: lines 791–796 use
  `floor(point.axis / downsample_size) * downsample_size` as the inclusive
  lower bound and lower bound plus `downsample_size` as the exclusive upper
  bound
- voxel_identity_source: `Day7_Box_Identity` at lines 573–578 hashes the exact
  six bounds produced above; the identity call occurs at line 839
- confidence: `CONFIRMED`
- notes: Day 8 may observe this existing query and its existing result vector.
  It must not issue a second range query or change representative selection.

## Public range-query entry

- source_file: `include/ikd-Tree/ikd_Tree.cpp`
- symbol: `KD_TREE<PointType>::Box_Search`
- line_range: 704–709
- source_sha256:
  `52166cb088f5efb9546bc82ecf09b1940118163039e0af8979d9b62c5c9ace78`
- formal_input: `Box_of_Point`
- formal_output: caller-provided `Storage`, cleared before recursion
- confidence: `CONFIRMED`
- notes: `Add_Points` does not call this public wrapper; it invokes the private
  recursive function directly.

## Recursive range search

- source_file: `include/ikd-Tree/ikd_Tree.cpp`
- symbol: `KD_TREE<PointType>::Search_by_range`
- line_range: 1935–1978
- source_sha256:
  `52166cb088f5efb9546bc82ecf09b1940118163039e0af8979d9b62c5c9ace78`
- formal_input: current `KD_TREE_NODE`, by-value `BoxPointType`, and the
  existing result `Storage`
- formal_output: valid points appended to `Storage`
- node_relation_enum:
  - `NO_INTERSECTION`: any axis satisfies
    `query.max <= node.min || query.min > node.max`
  - `FULL_COVER`: every axis satisfies
    `query.min <= node.min && query.max > node.max`
  - `PARTIAL_INTERSECTION`: neither condition above
- child_visit_order: current node, left subtree, right subtree
- point_visibility_conditions: `Push_Down(root)` first materializes pending
  deletion state; a partially intersecting current point is returned only when
  it is inside the half-open query box and `!root->point_deleted`
- subtree_visibility_conditions: full-cover uses
  `flatten(root, Storage, NOT_RECORD)`; `flatten` visits current, left, right
  and appends only points for which `!point_deleted`
- confidence: `CONFIRMED`
- notes: `tree_deleted` is not a separate return predicate in
  `Search_by_range`. Its effect is propagated by `Push_Down` into
  `point_deleted`; Day 8 records both flags without changing either.

## Full-cover traversal

- source_file: `include/ikd-Tree/ikd_Tree.cpp`
- symbol: `KD_TREE<PointType>::flatten`
- line_range: 2315–2345
- source_sha256:
  `52166cb088f5efb9546bc82ecf09b1940118163039e0af8979d9b62c5c9ace78`
- formal_input: full-cover subtree root and existing result `Storage`
- formal_output: preorder current/left/right valid points
- point_visibility_conditions: `Push_Down(root)` followed by
  `!root->point_deleted`
- confidence: `CONFIRMED`

## Deletion propagation

- source_file: `include/ikd-Tree/ikd_Tree.cpp`
- symbol: `KD_TREE<PointType>::Push_Down`
- line_range: 2048–2141
- source_sha256:
  `52166cb088f5efb9546bc82ecf09b1940118163039e0af8979d9b62c5c9ace78`
- point_visibility_conditions: parent `tree_deleted` and
  `tree_downsample_deleted` are propagated into child `tree_deleted`,
  `point_deleted`, invalid counts, and pending push flags
- subtree_visibility_conditions: a child equal to `*Rebuild_Ptr` is updated
  while holding the existing `working_flag_mutex`; the existing logger path is
  retained
- confidence: `CONFIRMED`

## Rebuild reader protocol

- source_file: `include/ikd-Tree/ikd_Tree.cpp`
- symbol: `KD_TREE<PointType>::Search_by_range` and
  `KD_TREE<PointType>::multi_thread_rebuild`
- line_range: 344–363, 438–468, 1957–1975
- source_sha256:
  `52166cb088f5efb9546bc82ecf09b1940118163039e0af8979d9b62c5c9ace78`
- rebuild_reader_protocol: recursion into a child that is exactly
  `*Rebuild_Ptr` is enclosed by the existing `search_flag_mutex`; other
  children recurse without that lock. The rebuild writer waits for the existing
  search counter protocol before flattening or replacing the subtree.
- locks_held: only the pre-existing `search_flag_mutex` around the affected
  child recursion; Day 8 must not add locks or widen this interval
- confidence: `CONFIRMED`

## Existing identities and runtime wiring

- source_file: `include/ikd-Tree/ikd_Tree.h`
- symbol: `KD_TREE`, `KD_TREE_NODE`, `Day7_Point_Identity`,
  `Day7_Box_Identity`
- line_range: 28–108, 284–351, 360–410
- source_sha256:
  `e8ca4cdd74aec6ae112a1ffdbbda0bd9d00734a7b0b4d8c14976798fa22685c3`
- voxel_identity_source: the six exact query-box bound bits
- point_visibility_conditions: existing `point_deleted` and `tree_deleted`
  flags only
- confidence: `CONFIRMED`

- source_file: `src/laserMapping.cpp`
- symbol: `map_incremental`, Day 7 context wiring, coherent snapshot hooks
- line_range: 711–757, 2028–2047
- source_sha256:
  `0bb9bf199bc11c29c3effba22ed35128bd4f4c0626de44723255dce2deb37ec0`
- formal_input: fixed `PointToAdd` and `PointNoNeedDownsample` batches
- formal_output: unchanged calls to `KD_TREE::Add_Points`
- confidence: `CONFIRMED`

## Safe Day 8 hook locations

- safe_query_summary_hook: begin immediately before the existing
  `Search_by_range` call in `Add_Points`; finish immediately after it using the
  unchanged `Downsample_Storage`
- safe_traversal_token_hook: copy only the current node flags, ranges, point
  identity, already-evaluated relation, child masks, and rebuild metadata inside
  the existing recursive call
- safe_snapshot_hook: use the coherent point copy already produced by the
  existing snapshot protocol and compute voxel identity in C++ from the exact
  `downsample_size` and formal half-open box formula
- locks_held: no new lock; no formal lock interval may be widened
- confidence: `CONFIRMED`
- notes: hooks are disabled by default, bounded, preallocated, and must not
  perform file I/O, sorting, sleeping, or additional tree queries on the hot
  path.
