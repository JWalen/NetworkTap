#!/usr/bin/env bash
# NetworkTap - Complete Uninstaller
# Removes all NetworkTap components for a clean reinstall
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
info() { echo -e "${CYAN}[i]${NC} $*"; }

INSTALL_DIR="/opt/networktap"

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[✗]${NC} Must be run as root"
    exit 1
fi

echo -e "${RED}"
echo "╔══════════════════════════════════════════════════╗"
echo "║       NetworkTap Complete Uninstaller            ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

echo "This will remove:"
echo "  - All NetworkTap services"
echo "  - Configuration files"
echo "  - Network configuration (systemd-networkd files)"
echo "  - Console customizations"
echo "  - Custom Zeek/Suricata configs deployed by NetworkTap"
echo ""

read -rp "Continue with uninstall? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || exit 0

read -rp "Also delete capture files and logs? [y/N] " delete_data
read -rp "Also remove Zeek and Suricata packages? [y/N] " remove_ids

# ── Stop and disable all services ────────────────────────────────
log "Stopping all NetworkTap services..."
for svc in networktap-capture networktap-suricata networktap-zeek networktap-web networktap-cleanup.timer networktap-cleanup.service networktap-console; do
    systemctl stop "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
done

# ── Restore console getty ────────────────────────────────────────
log "Restoring default console..."
systemctl unmask getty@tty1.service 2>/dev/null || true
systemctl enable getty@tty1.service 2>/dev/null || true

# ── Remove systemd units ─────────────────────────────────────────
log "Removing systemd units..."
rm -f /etc/systemd/system/networktap-*.service
rm -f /etc/systemd/system/networktap-*.timer

# ── Remove network configuration ─────────────────────────────────
log "Removing network configuration..."
rm -f /etc/systemd/network/10-*.network
rm -f /etc/systemd/network/10-*.netdev

# ── Remove bridge interface if exists ────────────────────────────
if ip link show br0 &>/dev/null; then
    log "Removing bridge interface br0..."
    ip link set br0 down 2>/dev/null || true
    ip link delete br0 type bridge 2>/dev/null || true
fi

# ── Remove custom Zeek config ────────────────────────────────────
log "Removing custom Zeek configurations..."
# Remove our custom local.zeek from Zeek's site directory
for zeek_site in /opt/zeek/share/zeek/site /usr/local/zeek/share/zeek/site /usr/share/zeek/site; do
    if [[ -f "${zeek_site}/local.zeek" ]]; then
        # Check if it's our custom one (contains NetworkTap comment)
        if grep -q "NetworkTap" "${zeek_site}/local.zeek" 2>/dev/null; then
            rm -f "${zeek_site}/local.zeek"
            log "  Removed ${zeek_site}/local.zeek"
        fi
    fi
done

# Remove /etc/zeek if we created it
if [[ -d /etc/zeek ]]; then
    rm -rf /etc/zeek
    log "  Removed /etc/zeek/"
fi

# Remove Zeek PATH addition
rm -f /etc/profile.d/zeek.sh

# ── Remove custom Suricata config ────────────────────────────────
log "Removing custom Suricata configurations..."
rm -f /etc/suricata/networktap.yaml
# Restore original suricata.yaml if we backed it up
if [[ -f /etc/suricata/suricata.yaml.orig ]]; then
    mv /etc/suricata/suricata.yaml.orig /etc/suricata/suricata.yaml
    log "  Restored original suricata.yaml"
fi

# ── Remove config files ──────────────────────────────────────────
log "Removing configuration files..."
rm -f /etc/networktap.conf
rm -f /etc/logrotate.d/networktap
rm -f /etc/issue.networktap

# ── Remove command symlinks ──────────────────────────────────────
log "Removing command symlinks..."
rm -f /usr/local/bin/networktap-status
rm -f /usr/local/bin/networktap-health

# ── Remove installation directory ────────────────────────────────
log "Removing ${INSTALL_DIR}..."
rm -rf "$INSTALL_DIR"

# ── Optionally remove data ───────────────────────────────────────
if [[ "$delete_data" =~ ^[Yy]$ ]]; then
    log "Removing capture data and logs..."
    rm -rf /var/lib/networktap
    rm -rf /var/log/networktap
    rm -f /var/log/networktap-install.log
    # Also clean Zeek logs if they exist
    rm -rf /var/log/zeek
    log "  Removed /var/log/zeek/"
fi

# ── Remove Zeek and Suricata packages ────────────────────────────
if [[ "$remove_ids" =~ ^[Yy]$ ]]; then
    log "Removing Zeek and Suricata packages..."

    # Stop any remaining processes
    systemctl stop suricata 2>/dev/null || true
    systemctl disable suricata 2>/dev/null || true

    # Remove Suricata
    if dpkg -l | grep -q suricata; then
        apt-get remove --purge -y suricata suricata-update 2>/dev/null || true
        rm -rf /etc/suricata
        rm -rf /var/lib/suricata
        rm -rf /var/log/suricata
        log "  Removed Suricata"
    fi

    # Remove Zeek
    if dpkg -l | grep -q zeek; then
        apt-get remove --purge -y zeek zeek-lts zeek-core 2>/dev/null || true
        log "  Removed Zeek package"
    fi

    # Remove Zeek if installed to /opt/zeek (manual/binary install)
    if [[ -d /opt/zeek ]]; then
        rm -rf /opt/zeek
        log "  Removed /opt/zeek"
    fi

    # Clean up Zeek logs
    rm -rf /var/log/zeek

    # Remove Zeek repo if we added it
    rm -f /etc/apt/sources.list.d/zeek.list
    rm -f /etc/apt/trusted.gpg.d/zeek.gpg

    # Clean up apt
    apt-get autoremove -y 2>/dev/null || true
fi

# ── Reload systemd ───────────────────────────────────────────────
log "Reloading systemd..."
systemctl daemon-reload

# ── Restart networking (optional) ────────────────────────────────
echo ""
read -rp "Restart networking now? (may disconnect SSH) [y/N] " restart_net
if [[ "$restart_net" =~ ^[Yy]$ ]]; then
    log "Restarting systemd-networkd..."
    systemctl restart systemd-networkd || true
fi

# ── Summary ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Uninstall Complete!                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
info "NetworkTap has been removed from this system."
echo ""
if [[ "$remove_ids" =~ ^[Yy]$ ]]; then
    info "Zeek and Suricata packages were removed."
else
    warn "The following were NOT removed (system packages):"
    echo "  - Suricata (apt remove --purge suricata)"
    echo "  - Zeek (apt remove --purge zeek)"
fi
echo ""
warn "Other packages NOT removed: tcpdump, dialog, python3, etc."
echo ""
info "You can now run install.sh for a fresh installation."
