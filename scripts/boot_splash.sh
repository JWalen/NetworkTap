#!/usr/bin/env bash
# NetworkTap Boot Splash - Displays system status on console
set -uo pipefail

# Load config
source /etc/networktap.conf 2>/dev/null || true

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# Clear screen
clear

# Get system info
HOSTNAME=$(hostname)
UPTIME=$(uptime -p 2>/dev/null || echo "unknown")
KERNEL=$(uname -r)

# Get management interface and IP
if [[ "${MODE:-span}" == "bridge" ]]; then
    MGMT_IFACE="${BRIDGE_NAME:-br0}"
else
    MGMT_IFACE="${NIC2:-eth0}"
fi

# Get IP address
MGMT_IP=$(ip -4 addr show "$MGMT_IFACE" 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1)
if [[ -z "$MGMT_IP" ]]; then
    MGMT_IP="No IP (check network)"
fi

# Check service status
check_service() {
    if systemctl is-active --quiet "$1" 2>/dev/null; then
        echo -e "${GREEN}running${NC}"
    else
        echo -e "${RED}stopped${NC}"
    fi
}

WEB_STATUS=$(check_service networktap-web)
CAPTURE_STATUS=$(check_service networktap-capture)
SURICATA_STATUS=$(check_service networktap-suricata)
ZEEK_STATUS=$(check_service networktap-zeek)

# Get disk usage
DISK_USAGE=$(df -h "${CAPTURE_DIR:-/var/lib/networktap/captures}" 2>/dev/null | awk 'NR==2 {print $5 " used (" $4 " free)"}')
[[ -z "$DISK_USAGE" ]] && DISK_USAGE="unknown"

# Get capture stats
PCAP_COUNT=$(find "${CAPTURE_DIR:-/var/lib/networktap/captures}" -name "*.pcap*" 2>/dev/null | wc -l)

# Display splash
echo -e "${CYAN}"
cat << 'EOF'
 _   _      _                      _    _____
| \ | | ___| |___      _____  _ __| | _|_   _|_ _ _ __
|  \| |/ _ \ __\ \ /\ / / _ \| '__| |/ / | |/ _` | '_ \
| |\  |  __/ |_ \ V  V / (_) | |  |   <  | | (_| | |_) |
|_| \_|\___|\__| \_/\_/ \___/|_|  |_|\_\ |_|\__,_| .__/
                                                 |_|
EOF
echo -e "${NC}"

APP_VERSION=$(cat /opt/networktap/VERSION 2>/dev/null || echo "unknown")
echo -e "  ${BOLD}NetworkTap v${APP_VERSION}${NC}"
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  System Information${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Hostname:     ${CYAN}${HOSTNAME}${NC}"
echo -e "  Kernel:       ${KERNEL}"
echo -e "  Uptime:       ${UPTIME}"
echo -e "  Mode:         ${CYAN}${MODE:-span}${NC}"
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Network${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Interface:    ${MGMT_IFACE}"
echo -e "  IP Address:   ${CYAN}${MGMT_IP}${NC}"
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Services${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Web UI:       ${WEB_STATUS}"
echo -e "  Capture:      ${CAPTURE_STATUS}"
echo -e "  Suricata:     ${SURICATA_STATUS}"
echo -e "  Zeek:         ${ZEEK_STATUS}"
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Storage${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Disk:         ${DISK_USAGE}"
echo -e "  PCAP files:   ${PCAP_COUNT}"
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Access${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [[ "$MGMT_IP" != "No IP"* ]]; then
    echo -e "  Web UI:       ${CYAN}http://${MGMT_IP}:${WEB_PORT:-8443}${NC}"
    echo -e "  SSH:          ${CYAN}ssh root@${MGMT_IP}${NC}"
else
    echo -e "  ${YELLOW}Waiting for network...${NC}"
fi
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
