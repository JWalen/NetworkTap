#!/usr/bin/env bash
# Configure Suricata IDS for NetworkTap
set -euo pipefail

source /etc/networktap.conf

if [[ "$SURICATA_ENABLED" != "yes" ]]; then
    echo "[i] Suricata disabled in config, skipping"
    exit 0
fi

if ! command -v suricata &>/dev/null; then
    echo "[!] Suricata not installed, skipping configuration"
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Determine capture interface
CAPTURE_IF="$NIC1"
if [[ "$MODE" == "bridge" ]]; then
    CAPTURE_IF="$BRIDGE_NAME"
fi
if [[ "$SURICATA_IFACE" != "auto" ]]; then
    CAPTURE_IF="$SURICATA_IFACE"
fi

echo "[+] Configuring Suricata on interface: ${CAPTURE_IF}"

# Backup original config
if [[ -f /etc/suricata/suricata.yaml ]] && [[ ! -f /etc/suricata/suricata.yaml.orig ]]; then
    cp /etc/suricata/suricata.yaml /etc/suricata/suricata.yaml.orig
fi

# Deploy our configuration
cp "${PROJECT_DIR}/config/suricata/suricata.yaml" /etc/suricata/suricata.yaml

# Set the interface in the config
sed -i "s/NETWORKTAP_IFACE/${CAPTURE_IF}/g" /etc/suricata/suricata.yaml

# Create log directory
mkdir -p "$SURICATA_LOG_DIR"

# Update rules
echo "[+] Updating Suricata rules..."
suricata-update 2>/dev/null || echo "[!] Rule update failed (non-fatal)"

# Test configuration
echo "[+] Testing Suricata configuration..."
if suricata -T -c /etc/suricata/suricata.yaml 2>/dev/null; then
    echo "[+] Suricata configuration valid"
else
    echo "[!] Suricata configuration test failed, check /etc/suricata/suricata.yaml"
fi

echo "[+] Suricata configuration complete"
