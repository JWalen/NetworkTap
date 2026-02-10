# NetworkTap - Zeek Local Policy
# Network tap / passive monitoring with JSON output

# Enable JSON logging
redef LogAscii::use_json = T;
redef LogAscii::json_timestamps = JSON::TS_ISO8601;

# Increase connection tracking timeout for tap environment
redef tcp_inactivity_timeout = 10 min;
redef udp_inactivity_timeout = 2 min;

# Load Zeek's standard local policy (includes common analyzers)
@load local
