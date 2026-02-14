#!/usr/bin/env bash
# Start tcpdump packet capture with rotation
set -euo pipefail

source /etc/networktap.conf

# Determine capture interface
if [[ "$CAPTURE_IFACE" == "auto" ]]; then
    if [[ "$MODE" == "bridge" ]]; then
        IFACE="$BRIDGE_NAME"
    else
        IFACE="$NIC1"
    fi
else
    IFACE="$CAPTURE_IFACE"
fi

PCAP_DIR="${CAPTURE_DIR}/active"
mkdir -p "$PCAP_DIR"

# Build tcpdump command
TCPDUMP_ARGS=(
    -i "$IFACE"
    -w "${PCAP_DIR}/capture_%Y%m%d_%H%M%S.pcap"
    -G "$CAPTURE_ROTATE_SECONDS"
    -n
)

# Snap length
if [[ "$CAPTURE_SNAPLEN" -gt 0 ]] 2>/dev/null; then
    TCPDUMP_ARGS+=(-s "$CAPTURE_SNAPLEN")
fi

# File limit
if [[ "$CAPTURE_FILE_LIMIT" -gt 0 ]] 2>/dev/null; then
    TCPDUMP_ARGS+=(-W "$CAPTURE_FILE_LIMIT")
fi

# Post-rotation compression
if [[ "$CAPTURE_COMPRESS" == "yes" ]]; then
    TCPDUMP_ARGS+=(-z gzip)
fi

# BPF filter
if [[ -n "${CAPTURE_FILTER:-}" ]]; then
    TCPDUMP_ARGS+=("$CAPTURE_FILTER")
fi

echo "[+] Starting capture on ${IFACE}"
echo "[+] Output: ${PCAP_DIR}"
echo "[+] Rotation: every ${CAPTURE_ROTATE_SECONDS}s"

# Store PID for stop script
exec tcpdump "${TCPDUMP_ARGS[@]}"
