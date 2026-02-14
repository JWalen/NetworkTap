#!/usr/bin/env bash
# NetworkTap - Zeek Startup Script
set -euo pipefail

# Load config
source /etc/networktap.conf

# Find Zeek binary
ZEEK_BIN=""
for p in /opt/zeek/bin/zeek /usr/local/zeek/bin/zeek /usr/bin/zeek; do
    if [[ -x "$p" ]]; then
        ZEEK_BIN="$p"
        break
    fi
done

if [[ -z "$ZEEK_BIN" ]]; then
    echo "ERROR: Zeek not found"
    exit 1
fi

ZEEK_BASE="$(dirname "$(dirname "$ZEEK_BIN")")"
echo "Using Zeek: $ZEEK_BIN (base: $ZEEK_BASE)"

# Determine interface
if [[ "${ZEEK_IFACE:-auto}" == "auto" || -z "${ZEEK_IFACE:-}" ]]; then
    if [[ "${MODE:-span}" == "bridge" ]]; then
        IFACE="${BRIDGE_NAME:-br0}"
    else
        IFACE="${NIC1:-eth0}"
    fi
else
    IFACE="$ZEEK_IFACE"
fi

echo "Monitoring interface: $IFACE"

# Wait for interface to be available (up to 30 seconds)
for i in {1..30}; do
    if ip link show "$IFACE" &>/dev/null; then
        break
    fi
    echo "Waiting for interface $IFACE... ($i/30)"
    sleep 1
done

if ! ip link show "$IFACE" &>/dev/null; then
    echo "ERROR: Interface $IFACE not found"
    exit 1
fi

# Set up log directory
LOG_DIR="${ZEEK_LOG_DIR:-/var/log/zeek}"
mkdir -p "$LOG_DIR"
echo "Log directory: $LOG_DIR"

# Run Zeek directly without loading local script
# This avoids issues with missing frameworks
echo "Starting Zeek..."
cd "$ZEEK_BASE"
exec "$ZEEK_BIN" -i "$IFACE" \
    LogAscii::use_json=T \
    LogAscii::json_timestamps=JSON::TS_ISO8601 \
    Log::default_logdir="$LOG_DIR"
