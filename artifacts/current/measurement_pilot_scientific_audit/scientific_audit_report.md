# Measurement Pilot Scientific Audit

## Technical summary

Primary conclusion: **B.
PILOT_LABEL_INVALIDATED**.

`MEASUREMENT_PLAN_STATUS=NEW_PREREGISTERED_REPLACEMENT_PILOT_REQUIRED`.  The nominal
control segment is consistently weaker than the structural candidate under
both absolute-strength and spectral-shape information families.  The frozen
label therefore does not measure the intended contrast.  The reference axis is
also insufficient for a sharp 30-degree decision, so the current evidence
cannot isolate a method-level negative result.  The original Pilot remains
FAIL; this audit is not a retrospective pass.

## The label failure is the primary decision driver

Structural/control median lambda-min is 11.901430/
3.696398; median condition number is
16.880643/52.617521.  Those absolute-strength and
shape diagnostics agree that the control is less observable.  ODI semantic
AUROC remains 0.001966772; labels
were neither swapped nor reselected to improve it.

The formal 3-D median weak-axis error is 30.705691
degrees, and its declared uncertainty interval
[15.705691, 45.705691] crosses
the 30-degree gate.  Half- and quarter-window reference axes are not stable.
This is a concurrent limitation, not category C overriding the stronger
category-B label evidence.

Two component evaluation defects were confirmed: eigengap/correlation semantics
and exact future-time interpolation.  Corrected evaluation v2 retains the same
bag, intervals, formulas, threshold, and five-second formal window and reruns
every original Gate condition.  No Gate or formal conclusion changes, so
`EVALUATION_BUG_CONFIRMED=false`.  ODI is analytically rank-equivalent to the
exported spectral entropy/effective rank, so independent ranking information is
not established.

## Scope, data, and metric definitions

The audit uses only the frozen MUN-FRL Lighthouse bag and the preregistered
1645814048-1645814062 structural and 1645814164-1645814178 control intervals.
The structural interval remains positive class 1.  Future error growth is the
change in globally rigid-aligned 3-D position error over the formal five-second
window.  LiDAR, IMU, FAST-LIO, and RTK timestamps are ROS message-header Unix
seconds; reference data is offline position-only ENU.

## Method and robustness checks

Metric polarity was derived from formulas before inspecting labels.  AUROC was
recomputed in raw, semantic, and reversed-diagnostic directions without using
`max(AUC, 1-AUC)`.  Future growth was checked with exact native-stream
interpolation and 1/3/5/10-second sensitivity windows.  A -2 to +2 second lag
grid was diagnostic only.  The full weak-axis frame chain was checked with
identity, X/Y/Z 90-degree, sign, forward-extrinsic, and fixed-seed random SO(3)
tests.  Label validity used independent absolute-information and spectral-shape
families; reliability uncertainty used bootstrap intervals, Mann-Whitney, and
Cliff's delta descriptively.

## Visual evidence map

- [ODI versus spectral entropy](figures/odi_vs_spectral_entropy.png) shows the exact exported monotonic relationship on 1,719 valid frames.
- [ODI versus effective rank](figures/odi_vs_effective_rank.png) shows the corresponding exact affine relationship.
- [Lag sensitivity](figures/time_lag_sensitivity.png) marks zero as the sole formal lag; the curve is diagnostic and was not optimized.
- [Weak direction and reference](figures/weak_direction_reference_overlay.png) compares both axes in ENU and exposes the reference's large Up component.
- [Translation eigenvalues](figures/interval_eigenvalue_timeline.png) shows that the frozen control has weaker minimum and middle information.
- [Correspondence support](figures/interval_correspondence_support.png) shows that higher control counts and map size do not imply stronger Schur information.
- [Reference trajectory](figures/reference_axis_trajectory.png) shows the 3-D centerline curvature/height contribution alongside its XY projection.
- [Eigengap reliability](figures/eigengap_vs_angle_error.png) shows the five-sample unreliable group and the frozen 0.02 threshold.
- [Trigger threshold transfer](figures/threshold_vs_real_distribution.png) shows every real frozen-interval ODI far above the synthetic threshold.

## Limitations and uncertainty

Plane-normal distributions, normal covariance, residual magnitudes, map
Cartesian extent, end-face counts, and floor/ceiling/wall ratios were not
retained and are explicitly unavailable.  RTK supplies motion position rather
than an independent environmental Schur-null axis; the antenna-to-IMU lever arm
was not recorded.  This is one sequence with only five unreliable structural
frames, so neither eigengap calibration nor cross-domain trigger calibration is
validated.

## Recommended next step

Authorize one newly preregistered replacement Pilot.  It must independently
validate both the LIO observability labels and a reference axis capable of
supporting the 30-degree decision before detector outputs are examined.  Do not
expand to a second dataset and do not authorize ODI Measurement mainline yet.

## Further questions

The replacement protocol must specify how environmental observability ground
truth is obtained independently of raw scan anisotropy, how reference-axis
uncertainty is calibrated, and what minimum reliable/unreliable sample counts
are required.  Real-domain trigger calibration is a later preregistered task;
it must not be tuned on this failed Pilot.

## Frozen prohibitions honored

No ODI/AIS/Schur/eigengap formula was changed.  No threshold was tuned.  No
interval was reselected or swapped.  No second dataset, visual sensor, weak
state updater, or ikd-tree investigation was used.  The original negative
artifact was not overwritten or deleted, and nothing was pushed.
