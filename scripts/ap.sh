#!/usr/bin/env bash
# WiFi Access Point Management Script
# Controls hostapd + dnsmasq for wireless hotspot

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="/etc/networktap.conf"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    log "ERROR: $*" >&2
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
    fi
}

load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
    else
        error "Config file not found: $CONFIG_FILE"
    fi
}

detect_wifi_interface() {
    for iface in /sys/class/net/*; do
        iface_name=$(basename "$iface")
        if [[ -d "$iface/wireless" ]] || [[ -d "$iface/phy80211" ]]; then
            echo "$iface_name"
            return 0
        fi
    done
    return 1
}

start_ap() {
    log "Starting WiFi Access Point..."
    
    # Check if enabled
    if [[ "${WIFI_AP_ENABLED:-no}" != "yes" ]]; then
        error "Access Point is disabled in config (WIFI_AP_ENABLED=no)"
    fi
    
    # Detect interface
    WIFI_IFACE=$(detect_wifi_interface) || error "No WiFi interface found"
    log "  Using interface: $WIFI_IFACE"
    
    # Configure interface
    local ap_ip="${WIFI_AP_IP:-192.168.42.1}"
    log "  Configuring IP: $ap_ip"
    ip addr flush dev "$WIFI_IFACE" 2>/dev/null || true
    ip addr add "${ap_ip}/24" dev "$WIFI_IFACE"
    ip link set "$WIFI_IFACE" up
    
    # Start hostapd
    log "  Starting hostapd..."
    if systemctl is-active hostapd >/dev/null 2>&1; then
        systemctl restart hostapd
    else
        systemctl start hostapd
    fi
    
    # Wait for hostapd to initialize
    sleep 2
    
    if ! systemctl is-active hostapd >/dev/null 2>&1; then
        error "Failed to start hostapd"
    fi
    
    # Start dnsmasq
    log "  Starting dnsmasq..."
    if systemctl is-active dnsmasq >/dev/null 2>&1; then
        systemctl restart dnsmasq
    else
        systemctl start dnsmasq
    fi
    
    if ! systemctl is-active dnsmasq >/dev/null 2>&1; then
        systemctl stop hostapd
        error "Failed to start dnsmasq"
    fi
    
    log "✓ Access Point started successfully"
    log "  SSID: ${WIFI_AP_SSID:-NetworkTap-Admin}"
    log "  Channel: ${WIFI_AP_CHANNEL:-11}"
    log "  IP: $ap_ip"
}

stop_ap() {
    log "Stopping WiFi Access Point..."
    
    # Stop services
    if systemctl is-active dnsmasq >/dev/null 2>&1; then
        log "  Stopping dnsmasq..."
        systemctl stop dnsmasq
    fi
    
    if systemctl is-active hostapd >/dev/null 2>&1; then
        log "  Stopping hostapd..."
        systemctl stop hostapd
    fi
    
    # Flush interface
    WIFI_IFACE=$(detect_wifi_interface) || true
    if [[ -n "${WIFI_IFACE:-}" ]]; then
        log "  Flushing interface: $WIFI_IFACE"
        ip addr flush dev "$WIFI_IFACE" 2>/dev/null || true
        ip link set "$WIFI_IFACE" down 2>/dev/null || true
    fi
    
    log "✓ Access Point stopped"
}

restart_ap() {
    log "Restarting WiFi Access Point..."
    stop_ap
    sleep 2
    start_ap
}

status_ap() {
    load_config
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "NetworkTap Access Point Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Configuration
    echo ""
    echo "Configuration:"
    echo "  Enabled: ${WIFI_AP_ENABLED:-no}"
    echo "  SSID: ${WIFI_AP_SSID:-NetworkTap-Admin}"
    echo "  Channel: ${WIFI_AP_CHANNEL:-11}"
    echo "  IP: ${WIFI_AP_IP:-192.168.42.1}"
    echo "  Subnet: ${WIFI_AP_SUBNET:-192.168.42.0/24}"
    
    # Interface
    echo ""
    echo "Interface:"
    WIFI_IFACE=$(detect_wifi_interface) && echo "  Name: $WIFI_IFACE" || echo "  Name: (not detected)"
    
    if [[ -n "${WIFI_IFACE:-}" ]]; then
        if ip link show "$WIFI_IFACE" >/dev/null 2>&1; then
            local state=$(cat /sys/class/net/"$WIFI_IFACE"/operstate 2>/dev/null || echo "unknown")
            echo "  State: $state"
            
            local ip_addr=$(ip -4 addr show "$WIFI_IFACE" | grep -oP 'inet \K[\d.]+' | head -1)
            echo "  IP: ${ip_addr:-(none)}"
        fi
    fi
    
    # Services
    echo ""
    echo "Services:"
    
    if command -v systemctl &>/dev/null; then
        local hostapd_status=$(systemctl is-active hostapd 2>/dev/null || echo "inactive")
        local dnsmasq_status=$(systemctl is-active dnsmasq 2>/dev/null || echo "inactive")
        
        echo "  hostapd: $hostapd_status"
        echo "  dnsmasq: $dnsmasq_status"
        
        if [[ "$hostapd_status" == "active" ]]; then
            echo ""
            echo "Connected Clients:"
            if command -v hostapd_cli &>/dev/null && [[ -e /var/run/hostapd/"$WIFI_IFACE" ]]; then
                local clients=$(hostapd_cli -i "$WIFI_IFACE" all_sta 2>/dev/null | grep -c "^[0-9a-fA-F][0-9a-fA-F]:" || echo "0")
                echo "  Count: $clients"
            else
                echo "  (hostapd_cli not available)"
            fi
        fi
    else
        echo "  (systemctl not available)"
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

list_clients() {
    check_root
    load_config
    
    WIFI_IFACE=$(detect_wifi_interface) || error "No WiFi interface found"
    
    echo "Connected Clients:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if ! systemctl is-active hostapd >/dev/null 2>&1; then
        echo "Access Point is not running"
        return 0
    fi
    
    if command -v hostapd_cli &>/dev/null && [[ -e /var/run/hostapd/"$WIFI_IFACE" ]]; then
        hostapd_cli -i "$WIFI_IFACE" all_sta 2>/dev/null | while read -r line; do
            if [[ $line =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]]; then
                echo "  MAC: $line"
            fi
        done
    else
        # Fallback: check dnsmasq leases
        if [[ -f /var/lib/misc/dnsmasq.leases ]]; then
            awk '{print "  " $2 " (" $3 ")"}' /var/lib/misc/dnsmasq.leases
        else
            echo "(No clients detected)"
        fi
    fi
}

usage() {
    cat << EOF
Usage: $0 {start|stop|restart|status|clients}

Commands:
  start    Start the WiFi Access Point
  stop     Stop the WiFi Access Point
  restart  Restart the WiFi Access Point
  status   Show current status
  clients  List connected clients

Config file: $CONFIG_FILE
EOF
    exit 1
}

main() {
    check_root
    load_config
    
    case "${1:-}" in
        start)
            start_ap
            ;;
        stop)
            stop_ap
            ;;
        restart)
            restart_ap
            ;;
        status)
            status_ap
            ;;
        clients)
            list_clients
            ;;
        *)
            usage
            ;;
    esac
}

main "$@"
