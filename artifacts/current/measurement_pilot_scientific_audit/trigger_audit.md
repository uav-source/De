# Trigger Audit

The predicate is `ODI_trans >= 0.035199792993590634`.  The threshold is
the locked 95th percentile of 2,080 synthetic Development Open-Control frames,
uses the same dimensionless ODI version, and is loaded only after source/config
hash verification.  Invalid lifecycle frames are not triggered.  The frozen
control segment triggers 139/
139 frames, and the whole real
sequence lies above the synthetic threshold.  The comparison sign, units,
fallback behavior, and lock path are correct.
`TRIGGER_IMPLEMENTATION_BUG_CONFIRMED=false` and
`REAL_DOMAIN_THRESHOLD_TRANSFER_FAILED=true`; no real-data recalibration was
performed.
