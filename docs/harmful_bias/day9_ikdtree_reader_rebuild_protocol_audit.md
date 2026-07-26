# Day 9 ikd-tree reader/rebuild protocol audit

## Scope and evidence boundary

This audit resolves the production reader/rebuild control flow that Day 9 is
authorized to exercise. Line numbers below refer to the frozen pre-Day-9
`include/ikd-Tree/ikd_Tree.cpp` whose SHA-256 is
`9989240da07641c4afb76ae41b00db2ffbba19f92a8cbeadb9f9f8dc79bf7eda`.
It does not claim that the identified window causes a production bug.

| Question | Resolution | Evidence |
|---|---|---|
| Does `KD_TREE::Box_Search` register a reader for the complete range search? | CONFIRMED: no | `ikd_Tree.cpp:728-732` clears storage and calls `Search_by_range` directly. It does not touch `search_flag_mutex` or `search_mutex_counter`. |
| Is protection acquired for every recursive child search? | CONFIRMED: no | `Search_by_range` at `2093-2105` and `2107-2119` takes `search_flag_mutex` only when the selected child is equal to `*Rebuild_Ptr` at the branch check. |
| Are the protection decision and child pointer load one atomic read? | CONFIRMED: no | The left condition reads `root->left_son_ptr` at `2093`, while the unprotected recursive call reads it again at `2096`. The right side has the same split at `2107` and `2110`. |
| Can a reader that chose the unprotected branch be counted later? | CONFIRMED: no automatic registration exists on that branch | The unprotected branches call recursively without incrementing `search_mutex_counter`. |
| When is a rebuild target published by normal production selection? | CONFIRMED | `KD_TREE::Rebuild` assigns `Rebuild_Ptr = root` at `1481-1489` for a subtree meeting the multithread rebuild threshold. |
| When does the rebuild thread exclude registered searches for its first flatten? | CONFIRMED | `multi_thread_rebuild` waits for counter zero and sets it to `-1` at `345-353`, then flattens the old target at `356`. It resets the counter to zero at `360-362`. |
| When is the parent child pointer exchanged? | CONFIRMED | The second exclusion phase is entered at `440-448`; the parent left or right pointer is assigned at `449-456`, and `*Rebuild_Ptr` is replaced at `463`. |
| When are the target and exclusion state cleared? | CONFIRMED | `search_mutex_counter` becomes zero at `504-506`; `Rebuild_Ptr` becomes null at `507`; `working_flag_mutex` is released at `508`. |
| When is the old subtree deleted? | CONFIRMED | `delete_tree_nodes(&old_root_node)` runs at `511`, after the counter reset, target clear, and working-mutex release. |
| Does the source prove that an already-unprotected reader is safe across swap/delete? | UNRESOLVED | No lifetime token, epoch, shared ownership, or complete-search reader registration covers a reader that passed the equality check before target publication. Day 9 must test this path without assuming an outcome. |
| Does `Push_Down` close the reader lifetime gap? | CONFIRMED: no | `Push_Down` conditionally serializes mutation of a child equal to `*Rebuild_Ptr` (`2203-2241`, `2246-2284`), but does not register the lifetime of an unprotected range reader. |
| Does `flatten` introduce an independent reader protocol? | CONFIRMED: no | `flatten` recursively reads both child pointers at `2460-2470` and relies on its caller's context. |
| What does `Rebuild_Logger` protect? | CONFIRMED | Operations observed while a target rebuild is active are queued and replayed onto the new subtree in `multi_thread_rebuild:375-436`. It does not register range readers or retain old nodes. |
| Is the Day 8 child-present field proof of recursive entry? | CONFIRMED: no | Day 8 snapshots child presence and target equality at `2005-2012`, records both child-considered and child-visited from that pre-recursion snapshot at `2032-2035`, and only afterwards performs the protection decision and recursive call at `2093-2119`. |

## Resolved protocol sequence

1. `Box_Search` enters `Search_by_range` without a whole-query reader token.
2. A partial node records a Day 8 snapshot before recursion.
3. For each child, `Search_by_range` compares the current child with the
   current rebuild target.
4. A nonmatching child follows an unprotected branch and loads the child
   pointer again for the recursive call.
5. The rebuild thread can publish a target, flatten the old target, construct
   and update a replacement, wait only for counted readers, swap the parent
   child pointer, clear the target, and delete the old tree.
6. The source contains no explicit lifetime registration for a range reader
   that passed the nonmatching decision before target publication.

## Day 9 source-path decision

`DAY9_SOURCE_PATH_RESOLUTION_PASS = true`.

The production source contains the exact decision/load/swap/delete path needed
for the authorized controlled schedules. Whether that path produces a member
omission, duplicate voxel members, or a memory-safety diagnostic remains
`UNRESOLVED` until the deterministic fixture is executed.
