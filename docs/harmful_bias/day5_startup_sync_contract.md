# Day 5 Startup-Sync V1 contract

The previous Day 5 remediation failed pure `AUDIT_ONLY` baseline repeatability because the third outdoor replay contained one extra leading `MeasureGroup`; its first divergence was scan 0 at `INPUT_GROUP`. Because all failing runs had the tap and observation export disabled, that failure cannot be attributed to the tap.

This remediation freezes one two-topic replay clip per Quick sequence. Each immutable clip contains only `/livox/lidar` and `/livox/imu`, uses the original bag start time and locked half-open duration window, and is an engineering replay derivative rather than a new scientific sequence.

Every replay follows the same startup protocol: start an isolated roscore, start `/laserMapping`, start `/day5_bag_player` with `--pause`, then verify the ROS master graph and both publisher/subscriber `getBusInfo` views. LiDAR and IMU must each have exactly one publisher and one subscriber, both TCPROS directions must be connected, and this state must remain true for 20 polls at 0.1 seconds. Only then may `/day5_bag_player/pause_playback` of type `std_srvs/SetBool` be called with `data: false`.

OMP and numerical-library thread counts, locale, playback rate, CPU affinity, FAST parameters, source tree, binary, runner, handshake checker and clip identities are locked. The first runtime row and first ten `MeasureGroup` identities must match exactly across all three repeats of each sequence. Scan indices are compared directly: no leading-frame deletion, timestamp offset, checksum search, or scan-index realignment is permitted.

The six pairwise baseline comparisons retain the existing strict `1e-12` numerical gates and exact checksums for input, prior, formal linearization, posterior, map size and final map. This task runs only six `AUDIT_ONLY` replays. It does not run `CAPTURE_ONLY`, `COMPACT_EXPORT`, detector processing, ODI or Day 6 diagnostics. Even a complete Stage A pass can authorize only a later capture/export remediation; `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED` remains false.
