# Day 8 Focused Traversal Witness Remediation Contract

This bounded diagnostic preserves formal FAST-LIO2 range-search, map update,
rebuild, locking, and thread behavior. Query summaries cover scans 155--165;
detailed traversal tokens cover exactly scans 156--158. Missing detailed-token
evidence is explicit and never treated as an empty traversal.

The offline shadow replay adjudicates a replacement of an occupied formal voxel
using the coherent pre-event member count: the full logical-map delta is
`1 - pre_event_member_count`. Runtime events are unchanged and the shadow state
never participates in FAST-LIO2 decisions.

Exactly four fixed quick-shack replays are authorized. Detector, ODI/AIS, weak
direction, feedback, GT, additional replays, commits, pushes, and Day 9 are not
authorized. Read-only instrumentation may perturb runtime timing.
