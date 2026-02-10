#!/usr/bin/env bash
# Install and enable systemd services for NetworkTap
set -euo pipefail

source /etc/networktap.conf

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICES_DIR="${PROJECT_DIR}/services"
SYSTEMD_DIR="/etc/systemd/system"

echo "[+] Installing systemd services..."

# Copy all service and timer files
for unit in "${SERVICES_DIR}"/*.service "${SERVICES_DIR}"/*.timer; do
    [[ -f "$unit" ]] || continue
    local_name="$(basename "$unit")"
    cp "$unit" "${SYSTEMD_DIR}/${local_name}"
    echo "  Installed: ${local_name}"
done

# Make scripts executable
chmod +x "${PROJECT_DIR}/scripts/"*.sh

# Create convenient command symlinks
ln -sf "${PROJECT_DIR}/scripts/status.sh" /usr/local/bin/networktap-status
ln -sf "${PROJECT_DIR}/scripts/health_check.sh" /usr/local/bin/networktap-health
echo "[+] Added commands: networktap-status, networktap-health"

# Reload systemd
systemctl daemon-reload

# Enable services
echo "[+] Enabling services..."
systemctl enable networktap-capture.service
systemctl enable networktap-web.service
systemctl enable networktap-cleanup.timer

if [[ "$SURICATA_ENABLED" == "yes" ]] && command -v suricata &>/dev/null; then
    systemctl enable networktap-suricata.service
fi

# Check for Zeek in known locations
ZEEK_FOUND=""
for p in /opt/zeek/bin/zeek /usr/local/zeek/bin/zeek /usr/bin/zeek; do
    [[ -x "$p" ]] && ZEEK_FOUND="$p" && break
done

if [[ "$ZEEK_ENABLED" == "yes" ]] && [[ -n "$ZEEK_FOUND" ]]; then
    echo "[+] Found Zeek at: $ZEEK_FOUND"
    systemctl enable networktap-zeek.service
fi

# Start services
echo "[+] Starting services..."
systemctl start networktap-capture.service
systemctl start networktap-web.service
systemctl start networktap-cleanup.timer

if [[ "$SURICATA_ENABLED" == "yes" ]] && command -v suricata &>/dev/null; then
    systemctl start networktap-suricata.service
fi

if [[ "$ZEEK_ENABLED" == "yes" ]] && [[ -n "$ZEEK_FOUND" ]]; then
    systemctl start networktap-zeek.service
fi

# Start console status display
systemctl start networktap-console.service 2>/dev/null || true

echo "[+] Service status:"
systemctl list-units --type=service --all 'networktap-*' --no-pager 2>/dev/null || true

echo "[+] Services configured and started"
