#!/usr/bin/env bash
# Configure tcpdump capture directory and rotation
set -euo pipefail

source /etc/networktap.conf

echo "[+] Setting up capture environment..."

# Create capture directory
mkdir -p "$CAPTURE_DIR"
chmod 750 "$CAPTURE_DIR"

# Create subdirectories
mkdir -p "${CAPTURE_DIR}/active"
mkdir -p "${CAPTURE_DIR}/archive"

# Set ownership (capture runs as root for raw sockets)
chown -R root:root "$CAPTURE_DIR"

# Verify tcpdump is available
if ! command -v tcpdump &>/dev/null; then
    echo "[!] tcpdump not found, install it first"
    exit 1
fi

# Set capabilities so tcpdump can be run more safely
# (still needs raw socket access)
setcap cap_net_raw,cap_net_admin=eip "$(command -v tcpdump)" 2>/dev/null || true

echo "[+] Capture directory: ${CAPTURE_DIR}"
echo "[+] Rotation: every ${CAPTURE_ROTATE_SECONDS}s"
echo "[+] Compression: ${CAPTURE_COMPRESS}"
echo "[+] Capture configuration complete"
