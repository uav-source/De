# Coordinate Frame Audit

The native primary weak direction is the minimum-eigenvalue direction of the
translation Schur matrix in FAST-LIO `camera_init` world/map coordinates.  The
tap only reorders native `[delta_p_world, delta_theta_body]` columns into
detector `[delta_theta_body, delta_p_world]`; it does not rotate translation.
The formal Jacobian is built from the current iterated in-call linearization
state `s`.  The scan-start prior is retained as metadata and the post-update
pose is not used to rotate the exported weak direction.  The forward
IMU-from-LiDAR extrinsic is already applied upstream while constructing the
formal Jacobian, so it must not be applied again to the world-frame weak axis.
The offline chain is only `v_ENU = R_enu_from_fast_world @ v_world`, followed by
`acos(abs(dot(unit(v_ENU), unit(axis_ENU))))`.  Kabsch translation is correctly
excluded from direction transformation.  ENU, not NED, is used.  Unit/X/Y/Z,
forward LiDAR-to-IMU-to-world, sign, and fixed-seed random SO(3) tests pass to
1e-12.  `FRAME_TRANSFORM_BUG_CONFIRMED=false`.

Remaining limitations are position-only Kabsch non-main-axis observability, an
unrecorded GNSS-antenna-to-IMU lever arm, and deletion of the large observation
binary under the original retention policy.  They are not confirmed frame bugs.
