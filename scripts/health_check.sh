#!/usr/bin/env bash
# Health check for all NetworkTap components
set -euo pipefail

source /etc/networktap.conf

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "  ${YELLOW}!${NC} $*"; WARNINGS=$((WARNINGS + 1)); }

ERRORS=0
WARNINGS=0

echo "NetworkTap Health Check"
echo "═══════════════════════"
echo ""

# ── Services ──
echo "Services:"
for svc in networktap-web networktap-suricata networktap-zeek networktap-capture; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        ok "${svc}: running"
    elif systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        fail "${svc}: enabled but not running"
    else
        warn "${svc}: not enabled"
    fi
done

# Cleanup timer
if systemctl is-active --quiet networktap-cleanup.timer 2>/dev/null; then
    ok "cleanup timer: active"
else
    warn "cleanup timer: inactive"
fi
echo ""

# ── Network Interfaces ──
echo "Network Interfaces:"
for iface in "$NIC1" "$NIC2"; do
    if ip link show "$iface" &>/dev/null; then
        state=$(ip link show "$iface" | grep -oP 'state \K\S+')
        if [[ "$state" == "UP" ]]; then
            ok "${iface}: UP"
        else
            fail "${iface}: ${state}"
        fi
    else
        fail "${iface}: not found"
    fi
done

if [[ "$MODE" == "bridge" ]]; then
    if ip link show "$BRIDGE_NAME" &>/dev/null; then
        ok "${BRIDGE_NAME}: exists"
    else
        fail "${BRIDGE_NAME}: bridge not found"
    fi
fi
echo ""

# ── Disk Space ──
echo "Storage:"
DISK_USAGE=$(df "$CAPTURE_DIR" 2>/dev/null | awk 'NR==2 {print $5}' | tr -d '%')
DISK_FREE=$((100 - ${DISK_USAGE:-100}))
DISK_AVAIL=$(df -h "$CAPTURE_DIR" 2>/dev/null | awk 'NR==2 {print $4}')

if [[ "$DISK_FREE" -gt 20 ]]; then
    ok "Disk: ${DISK_USAGE}% used (${DISK_AVAIL} available)"
elif [[ "$DISK_FREE" -gt "$MIN_FREE_DISK_PCT" ]]; then
    warn "Disk: ${DISK_USAGE}% used (${DISK_AVAIL} available)"
else
    fail "Disk: ${DISK_USAGE}% used - CRITICAL"
fi

# Count pcap files
PCAP_COUNT=$(find "$CAPTURE_DIR" \( -name "*.pcap" -o -name "*.pcap.gz" \) 2>/dev/null | wc -l)
PCAP_SIZE=$(du -sh "$CAPTURE_DIR" 2>/dev/null | awk '{print $1}')
ok "Captures: ${PCAP_COUNT} files (${PCAP_SIZE:-0})"
echo ""

# ── System Resources ──
echo "System:"
CPU_LOAD=$(awk '{print $1}' /proc/loadavg)
MEM_USED=$(free -m | awk 'NR==2 {printf "%.0f", $3/$2*100}')
UPTIME=$(uptime -p 2>/dev/null || uptime | sed 's/.*up //' | sed 's/,.*//')

ok "CPU Load: ${CPU_LOAD}"
if [[ "$MEM_USED" -lt 80 ]]; then
    ok "Memory: ${MEM_USED}% used"
elif [[ "$MEM_USED" -lt 95 ]]; then
    warn "Memory: ${MEM_USED}% used"
else
    fail "Memory: ${MEM_USED}% used - CRITICAL"
fi
ok "Uptime: ${UPTIME}"
echo ""

# ── Suricata ──
if [[ "$SURICATA_ENABLED" == "yes" ]]; then
    echo "Suricata:"
    if [[ -f "$SURICATA_EVE_LOG" ]]; then
        EVE_SIZE=$(du -h "$SURICATA_EVE_LOG" | awk '{print $1}')
        ALERT_COUNT=$(grep -c '"event_type":"alert"' "$SURICATA_EVE_LOG" 2>/dev/null || echo 0)
        ok "EVE log: ${EVE_SIZE} (${ALERT_COUNT} alerts)"
    else
        warn "EVE log not found"
    fi
    echo ""
fi

# ── Summary ──
echo "═══════════════════════"
if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
    echo -e "${GREEN}All checks passed${NC}"
elif [[ $ERRORS -eq 0 ]]; then
    echo -e "${YELLOW}${WARNINGS} warning(s)${NC}"
else
    echo -e "${RED}${ERRORS} error(s), ${WARNINGS} warning(s)${NC}"
fi

exit "$ERRORS"
