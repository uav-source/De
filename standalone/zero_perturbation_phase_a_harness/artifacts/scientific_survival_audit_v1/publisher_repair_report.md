# Publisher Repair Report

The compact Development artifact was restored without rerunning registration or analysis.

- Changed runtime file: `src/phase_a_harness/full_synthetic_publisher.py`
- Changed call at line 174: `Axes.boxplot(tick_labels=...)` → `Axes.boxplot(labels=...)`
- Frozen Matplotlib: `3.8.2`
- The frozen formal public entry rejected the post-freeze code hash, as designed.
- Publication therefore used the same publisher's internal atomic staging and double-verification path with the frozen manifest, primary analysis, independent verification, run manifest, and raw inventory.
- Compact artifact required files: `38`
- SHA missing / mismatch / unexpected: `0 / 0 / 0`
- `ARTIFACT_PUBLICATION_PASS = true`
- `trial_rerun_count = 0`; `snapshot_regeneration_count = 0`.

The complete change-boundary evidence is in `publisher_only_change_scope.json`.
