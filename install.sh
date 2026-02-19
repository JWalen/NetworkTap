#!/usr/bin/env bash
# NetworkTap - Master Installer
# OnLogic FR201 Network Tap Appliance
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_FILE="${SCRIPT_DIR}/networktap.conf"
INSTALL_DIR="/opt/networktap"
LOG_FILE="/var/log/networktap-install.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[!]${NC} $*" | tee -a "$LOG_FILE"; }
err()  { echo -e "${RED}[✗]${NC} $*" | tee -a "$LOG_FILE"; }
info() { echo -e "${CYAN}[i]${NC} $*" | tee -a "$LOG_FILE"; }

banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║         NetworkTap Installer v1.0.9              ║"
    echo "║      OnLogic FR201/FR202 Network Tap Appliance     ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        err "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_os() {
    if [[ ! -f /etc/debian_version ]]; then
        warn "This installer is designed for Debian/Ubuntu systems"
        read -rp "Continue anyway? [y/N] " confirm
        [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
    fi
    info "OS: $(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
}

detect_nics() {
    info "Detecting network interfaces..."
    local nics=()
    for iface in /sys/class/net/*; do
        iface="$(basename "$iface")"
        [[ "$iface" == "lo" ]] && continue
        [[ -d "/sys/class/net/${iface}/device" ]] && nics+=("$iface")
    done

    if [[ ${#nics[@]} -lt 2 ]]; then
        warn "Found ${#nics[@]} physical NIC(s): ${nics[*]:-none}"
        warn "NetworkTap requires 2 NICs for full functionality"
        if [[ ${#nics[@]} -eq 1 ]]; then
            warn "Single-NIC mode: using ${nics[0]} for both capture and management"
        fi
    else
        log "Found ${#nics[@]} NICs: ${nics[*]}"
    fi

    # Update config if NICs differ from defaults
    if [[ ${#nics[@]} -ge 2 ]]; then
        sed -i "s/^NIC1=.*/NIC1=${nics[0]}/" "$CONF_FILE"
        sed -i "s/^NIC2=.*/NIC2=${nics[1]}/" "$CONF_FILE"
        log "NIC1 (capture/bridge): ${nics[0]}"
        log "NIC2 (management/bridge): ${nics[1]}"
    elif [[ ${#nics[@]} -eq 1 ]]; then
        sed -i "s/^NIC1=.*/NIC1=${nics[0]}/" "$CONF_FILE"
        sed -i "s/^NIC2=.*/NIC2=${nics[0]}/" "$CONF_FILE"
    fi
}

install_files() {
    log "Installing NetworkTap to ${INSTALL_DIR}..."
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR"/
    chmod -R 755 "$INSTALL_DIR"

    # Create symlink for config
    ln -sf "${INSTALL_DIR}/networktap.conf" /etc/networktap.conf

    # Create required directories
    source "$CONF_FILE"
    mkdir -p "$CAPTURE_DIR" "$LOG_DIR" /var/lib/networktap
    chmod 750 "$CAPTURE_DIR"
}

run_setup_scripts() {
    local setup_dir="${SCRIPT_DIR}/setup"
    local scripts=(
        "install_dependencies.sh"
        "configure_network.sh"
        "configure_suricata.sh"
        "configure_zeek.sh"
        "configure_capture.sh"
        "configure_firewall.sh"
        "configure_services.sh"
        "configure_console.sh"
        "configure_display.sh"
        "configure_ai.sh"
    )

    for script in "${scripts[@]}"; do
        local script_path="${setup_dir}/${script}"
        if [[ -f "$script_path" ]]; then
            log "Running ${script}..."
            bash "$script_path" 2>&1 | tee -a "$LOG_FILE"
            if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
                err "Failed: ${script}"
                err "Check log: ${LOG_FILE}"
                exit 1
            fi
            log "Completed: ${script}"
        else
            warn "Missing setup script: ${script}"
        fi
    done
}

print_summary() {
    source "$CONF_FILE"
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         Installation Complete!                   ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    info "Mode:       ${MODE}"
    info "NIC1:       ${NIC1}"
    info "NIC2:       ${NIC2}"
    info "Captures:   ${CAPTURE_DIR}"
    info "Web UI:     http://<management-ip>:${WEB_PORT}"
    info "Credentials: ${WEB_USER} / ${WEB_PASS}"
    echo ""
    info "Service commands:"
    echo "  systemctl status networktap-*"
    echo "  systemctl restart networktap-web"
    echo ""
    info "Logs: ${LOG_DIR}"
    info "Install log: ${LOG_FILE}"
    echo ""
    warn "IMPORTANT: Change the default web password!"
    warn "Edit /etc/networktap.conf and restart networktap-web"
    echo ""
    log "System will reboot in 10 seconds to apply all changes..."
    log "Press Ctrl+C to cancel reboot"
    for i in 10 9 8 7 6 5 4 3 2 1; do
        echo -n "$i... "
        sleep 1
    done
    echo ""
    log "Rebooting now..."
    sync
    /sbin/reboot
}

# ── Main ─────────────────────────────────────────────────────────
main() {
    banner
    check_root
    check_os
    detect_nics
    install_files
    run_setup_scripts
    print_summary
}

main "$@"
