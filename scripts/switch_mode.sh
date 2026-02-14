#!/usr/bin/env bash
# Switch between SPAN and Bridge operating modes
set -euo pipefail

CONF_FILE="/etc/networktap.conf"
source "$CONF_FILE"

usage() {
    echo "Usage: $0 <span|bridge>"
    echo "  span   - NIC1 captures SPAN traffic, NIC2 for management"
    echo "  bridge - Both NICs form transparent bridge"
    exit 1
}

[[ $# -eq 1 ]] || usage

NEW_MODE="$1"
case "$NEW_MODE" in
    span|bridge) ;;
    *) usage ;;
esac

if [[ "$NEW_MODE" == "$MODE" ]]; then
    echo "[i] Already in ${MODE} mode"
    exit 0
fi

echo "[+] Switching from ${MODE} to ${NEW_MODE} mode..."

# Stop dependent services
echo "[+] Stopping capture services..."
systemctl stop networktap-capture.service 2>/dev/null || true
systemctl stop networktap-suricata.service 2>/dev/null || true
systemctl stop networktap-zeek.service 2>/dev/null || true

# Update config file
sed -i "s/^MODE=.*/MODE=${NEW_MODE}/" "$CONF_FILE"

# Re-run network configuration
echo "[+] Reconfiguring network..."
bash /opt/networktap/setup/configure_network.sh

# Re-run firewall configuration
echo "[+] Reconfiguring firewall..."
bash /opt/networktap/setup/configure_firewall.sh

# Update Suricata and Zeek interface
if [[ "$NEW_MODE" == "bridge" ]]; then
    CAPTURE_IF="${BRIDGE_NAME}"
else
    CAPTURE_IF="${NIC1}"
fi

# Update Suricata config
if [[ -f /etc/suricata/suricata.yaml ]]; then
    sed -i "s/interface: .*/interface: ${CAPTURE_IF}/" /etc/suricata/suricata.yaml
fi

# Restart services
echo "[+] Restarting services..."
systemctl restart networktap-web.service

if [[ "$SURICATA_ENABLED" == "yes" ]]; then
    systemctl start networktap-suricata.service 2>/dev/null || true
fi

if [[ "$ZEEK_ENABLED" == "yes" ]]; then
    systemctl start networktap-zeek.service 2>/dev/null || true
fi

echo "[+] Switched to ${NEW_MODE} mode"
echo "[i] Capture service not auto-started. Start manually if needed:"
echo "    systemctl start networktap-capture"
