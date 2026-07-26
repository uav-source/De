# Time Alignment Audit

LiDAR, raw IMU, FAST-LIO odometry, and `/fix` all use ROS message-header seconds.
Bag record epochs differ from headers by roughly 102 million seconds and are
not used.  FAST-LIO applies the frozen LiDAR-to-IMU offset `0.0034 s` by
subtracting it from IMU header time; automatic time sync is disabled.  The
formal RTK lag is exactly zero.  At lag zero, aligned position RMSE is
0.357956 m and ODI/future-growth
Spearman is -0.172954.  The full -2 to +2 s grid is
reported only as sensitivity; no statistically favorable lag is selected or
installed.  `TIME_ALIGNMENT_BUG_CONFIRMED=false`.
