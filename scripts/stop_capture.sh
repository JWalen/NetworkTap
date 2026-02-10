#!/usr/bin/env bash
# Gracefully stop tcpdump capture
set -euo pipefail

echo "[+] Stopping capture..."

# Find and signal tcpdump processes started by our service
pkill -SIGTERM -f "tcpdump.*networktap" 2>/dev/null || true

# Wait for graceful shutdown
sleep 2

# Force kill if still running
if pgrep -f "tcpdump.*networktap" &>/dev/null; then
    echo "[!] Force stopping capture..."
    pkill -SIGKILL -f "tcpdump.*networktap" 2>/dev/null || true
fi

echo "[+] Capture stopped"
