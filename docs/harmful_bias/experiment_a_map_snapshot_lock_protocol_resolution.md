# Experiment A Map Snapshot Lock Protocol Resolution

Status: `MAP_SNAPSHOT_LOCK_PROTOCOL_CONFIRMED=true`

Implementation selection:
`NEW_READONLY_SYNCHRONIZED_KDTREE_API` (scheme B).

This resolution is limited to a read-only snapshot invoked by the FAST-LIO2
estimator thread at the two audited quiescent hooks. It confirms synchronization
against the existing background rebuild thread. It does not claim that arbitrary
concurrent callers of every public KD_TREE API are supported, that a data race
has been proved, or that ikd-tree caused the original Day 6 branch.

## Audited source identity

| Source | Pre-remediation SHA-256 | Confidence |
|---|---|---|
| `include/ikd-Tree/ikd_Tree.h` | `bb87cab944c6c59e0be61cb0b3a2cd0e334d93dc1bf768875058857278135a4b` | CONFIRMED |
| `include/ikd-Tree/ikd_Tree.cpp` | `ec3cbbbb6386eb6c68f9aa081c48b5d62209ada44fe167a002d4e3b112a1ea9f` | CONFIRMED |

## Mutex and lifetime protocol

| mutex_or_guard | owner | protected_objects | acquire_sites | release_sites | lock_order | confidence | notes |
|---|---|---|---|---|---|---|---|
| `rebuild_ptr_mutex_lock` | `KD_TREE` | `Rebuild_Ptr`, complete background rebuild selection/flatten/build/commit/old-node disposal interval | `multi_thread_rebuild` 239; `Rebuild` 741 | `multi_thread_rebuild` 360; `Rebuild` 747 | first for background rebuild and coherent snapshot | CONFIRMED | Background thread retains it through old-tree deletion. |
| `working_flag_mutex` | `KD_TREE` | active-tree writes while a rebuild is active, rebuild logger handoff, commit-side metadata | `multi_thread_rebuild` 240 and 286; mutation paths 532/560/646 | matching unlocks | after `rebuild_ptr_mutex_lock` when both are held | CONFIRMED | No audited path acquires `rebuild_ptr_mutex_lock` while already holding this mutex. |
| `search_flag_mutex` plus `search_mutex_counter` | `KD_TREE` | reader admission to the subtree selected by `Rebuild_Ptr`; `-1` excludes readers during flatten/commit | rebuild 260–277 and 307–350; `Nearest_Search` 437–449; recursive `Search` branches 1109–1239 in the pre-remediation source | matching counter decrement/unlock | rebuild uses it only after rebuild/working ownership | CONFIRMED | This is the formal search reader lifetime protocol for the selected subtree. |
| `rebuild_logger_mutex_lock` | `KD_TREE` | `Rebuild_Logger` | rebuild replay 287–303; active-rebuild mutation paths | matching unlocks | nested under `working_flag_mutex` | CONFIRMED | Operations arriving during rebuild are replayed into the newly built subtree. |
| `points_deleted_rebuild_mutex_lock` | `KD_TREE` | deleted-point caches used by flatten/rebuild | rebuild 270–273; `acquire_removed_points` | matching unlocks | inside rebuild/search exclusion | CONFIRMED | Not needed by the new read-only collector because it does not record deleted points. |
| per-node `push_down_mutex_lock` | `KD_TREE_NODE` | lazy push-down execution in formal search | `Search` 1073–1083 in the pre-remediation source | matching unlocks | local to search | CONFIRMED | The snapshot does not invoke `Push_Down`; it interprets inherited lazy-delete flags without mutation. |

Line numbers in the table identify the audited pre-remediation implementation
where practical. The final source-lock evidence records post-remediation line
numbers and hashes.

## Protocol answers

1. **How does formal Nearest_Search avoid freed nodes?** When traversal reaches
   the subtree currently named by `Rebuild_Ptr`, it admits itself through
   `search_flag_mutex`, increments `search_mutex_counter`, traverses, and
   decrements on exit. Rebuild sets the counter to `-1` only after the active
   reader count reaches zero, and does not free `old_root_node` until commit has
   reopened reader admission.
2. **What happens during rebuild?** The background thread owns
   `rebuild_ptr_mutex_lock`, then `working_flag_mutex`; it excludes selected
   subtree readers for flatten, reopens them while building and logging formal
   mutations, excludes them again for pointer replacement, then clears
   `Rebuild_Ptr` and deletes the old subtree before releasing
   `rebuild_ptr_mutex_lock`.
3. **Is public flatten a safe snapshot API?** No. `flatten` has no global lock
   acquisition and calls mutating `Push_Down`. Calling it externally on
   `Root_Node` is not a coherent read-only snapshot.
4. **Was there an existing reusable stable snapshot API?** No.
5. **What is the minimum supported copy critical section?** Acquire
   `rebuild_ptr_mutex_lock`, then `working_flag_mutex`; read start metadata,
   traverse without `Push_Down`, copy point values, read end metadata; release
   `working_flag_mutex`, then `rebuild_ptr_mutex_lock`. Digesting, sorting,
   serialization, logging, and plotting occur after release.
6. **Is there an inverse lock order?** No inverse
   `working_flag_mutex -> rebuild_ptr_mutex_lock` acquisition was found in the
   audited source. The snapshot uses the same two-lock order as
   `multi_thread_rebuild`.
7. **Does background rebuild preserve the intended logical valid-point set?**
   Yes at the protocol/algorithm-intent level: it flattens valid points, builds
   a replacement, and replays logged Add/Delete operations before commit.
   Generation change alone is therefore not classified as logical-map content
   change. This is not a causal proof about the previous anomalous snapshot.

## New snapshot API

Symbol: `KD_TREE<PointType>::Snapshot_Valid_Points_Coherent`

Files:

- `include/ikd-Tree/ikd_Tree.h`
- `include/ikd-Tree/ikd_Tree.cpp`

Method identity:
`KD_TREE_REBUILD_PTR_THEN_WORKING_MUTEX_COPY_V1`

Maximum attempts: 3. A successful copy reports
`COHERENT_SYNCHRONIZED_COPY` only when valid counts, rebuild generation, and
logical mutation counter remain equal across the locked copy. The lock may
slightly perturb background rebuild timing; it does not alter a formal branch,
rebuild trigger, Add/Delete result, or Nearest_Search result.

