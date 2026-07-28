# Phase A v1 Run Authorization Invalidation

The Phase A v1 static protocol contract remains a valid historical lock, but its
formal run authorization is invalidated.  The locked runner at commit
`21d1ceb14907f78d9bb7e81ed2f70908c7ba3ebd` validates its inputs and then
unconditionally raises a `RuntimeError` stating that the execution body was
deferred.  It cannot generate a snapshot or execute a backend trial.

This is an engineering execution-contract failure.  It is not an Open3D
failure, a PCL failure, a scientific solver failure, or a failed Phase A result.
No v1 Phase A snapshot or formal trial was executed.

The original v1 lock artifact and decision are retained without modification.
Any future formal run requires a separately versioned implementation lock with
a non-placeholder runner.

