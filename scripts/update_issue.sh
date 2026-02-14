#!/usr/bin/env bash
# NetworkTap - Update /etc/issue with current status
# This displays above the login prompt on the console

source /etc/networktap.conf 2>/dev/null || true

# Get management interface and IP
if [[ "${MODE:-span}" == "bridge" ]]; then
    MGMT_IFACE="${BRIDGE_NAME:-br0}"
else
    MGMT_IFACE="${NIC2:-eth1}"
fi

# Get IP address (may take a moment after boot)
for i in {1..10}; do
    MGMT_IP=$(ip -4 addr show "$MGMT_IFACE" 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1)
    [[ -n "$MGMT_IP" ]] && break
    sleep 1
done
[[ -z "$MGMT_IP" ]] && MGMT_IP="Waiting for DHCP..."

# Check services
check_svc() {
    systemctl is-active --quiet "$1" 2>/dev/null && echo "UP" || echo "--"
}

WEB=$(check_svc networktap-web)
CAP=$(check_svc networktap-capture)
SURI=$(check_svc networktap-suricata)
ZEEK=$(check_svc networktap-zeek)

# Generate /etc/issue (plain text for serial console fallback)
cat > /etc/issue << 'LOGO'

  ███╗   ██╗███████╗████████╗██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗████████╗ █████╗ ██████╗
  ████╗  ██║██╔════╝╚══██╔══╝██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝╚══██╔══╝██╔══██╗██╔══██╗
  ██╔██╗ ██║█████╗     ██║   ██║ █╗ ██║██║   ██║██████╔╝█████╔╝    ██║   ███████║██████╔╝
  ██║╚██╗██║██╔══╝     ██║   ██║███╗██║██║   ██║██╔══██╗██╔═██╗    ██║   ██╔══██║██╔═══╝
  ██║ ╚████║███████╗   ██║   ╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗   ██║   ██║  ██║██║
  ╚═╝  ╚═══╝╚══════╝   ╚═╝    ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝

                            Network Monitoring Appliance
  ═══════════════════════════════════════════════════════════════════════════════════
LOGO

cat >> /etc/issue << EOF

    Mode:       ${MODE:-span}
    IP:         ${MGMT_IP}
    Web UI:     http://${MGMT_IP}:${WEB_PORT:-8443}
    SSH:        ssh root@${MGMT_IP}

    Services:   Web:${WEB}  Capture:${CAP}  Suricata:${SURI}  Zeek:${ZEEK}

======================================================================

EOF
