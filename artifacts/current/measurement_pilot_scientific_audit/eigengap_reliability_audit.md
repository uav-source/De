# Eigengap Reliability Audit

Reliability uses `(lambda_2-lambda_1)/lambda_max >= 0.02`, ascending eigenvalues,
and finite outputs.  Structural frames comprise 134
reliable and 5 unreliable frames.  Their
median 3-D errors are 30.800325 and
28.979868 degrees.  Bootstrap
intervals, Mann-Whitney, and Cliff's delta are descriptive only.

The current pilot cannot validate eigengap calibration because the unreliable group contains insufficient samples.

`RELIABILITY_VALIDATION_SUFFICIENT=false`; this is not a claim that eigengap is
invalid, and the threshold was not recalibrated.
