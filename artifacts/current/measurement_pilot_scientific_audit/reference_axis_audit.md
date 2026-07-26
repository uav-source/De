# Reference Axis Audit

The frozen ENU axis is the normalized difference of position-only RTK points
interpolated at the structural interval endpoints.  Its 3-D baseline includes a
4.4 m height change and has declared uncertainty +/-15 degrees without a stated
confidence level.  Formal 3-D median weak-axis error is
30.705691 degrees; applying the declared bound yields
[15.705691, 45.705691], which
straddles the 30-degree gate.  Horizontal XY median error is
10.211231 degrees but is diagnostic only and does not
replace the preregistered 3-D result.  RTK motion direction is also not an
independent measurement of the environmental Schur null direction.  Within the
same 14-second interval, the two half-window endpoint axes differ by
65.723087 degrees and the maximum quarter-window
pair differs by 88.290862 degrees.
The globally aligned LIO motion axis agrees within
2.241972 degrees, but that only confirms
motion consistency and cannot validate an environmental null axis.
`REFERENCE_INSUFFICIENT=true`; this cannot be written as an algorithm pass.
