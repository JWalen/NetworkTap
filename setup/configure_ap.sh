#!/usr/bin/env bash
# Configure WiFi Access Point (hostapd + dnsmasq)
# Creates a wireless hotspot for NetworkTap management

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /etc/networktap.conf 2>/dev/null || true

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

install_packages() {
    log "Installing required packages..."
    apt-get update -qq
    apt-get install -y -qq hostapd dnsmasq iptables
    
    # Stop services for configuration
    systemctl stop hostapd 2>/dev/null || true
    systemctl stop dnsmasq 2>/dev/null || true
    systemctl disable hostapd 2>/dev/null || true
    systemctl disable dnsmasq 2>/dev/null || true
}

detect_wifi_interface() {
    log "Detecting WiFi interface..."
    
    for iface in /sys/class/net/*; do
        iface_name=$(basename "$iface")
        if [[ -d "$iface/wireless" ]] || [[ -d "$iface/phy80211" ]]; then
            echo "$iface_name"
            return 0
        fi
    done
    
    error "No WiFi interface found"
}

check_wifi_capability() {
    local iface="$1"
    
    log "Checking WiFi capabilities..."
    
    if ! command -v iw &>/dev/null; then
        log "  Installing iw..."
        apt-get install -y -qq iw
    fi
    
    # Check if AP mode is supported
    if iw list 2>/dev/null | grep -q "AP"; then
        log "  ✓ AP mode supported"
        return 0
    else
        log "  ⚠ WARNING: AP mode may not be fully supported"
        return 0  # Continue anyway
    fi
}

create_hostapd_config() {
    local iface="$1"
    local ssid="${WIFI_AP_SSID:-NetworkTap-Admin}"
    local passphrase="${WIFI_AP_PASSPHRASE:-networktap123}"
    local channel="${WIFI_AP_CHANNEL:-11}"
    
    log "Creating hostapd configuration..."
    
    cat > /etc/hostapd/hostapd.conf << EOF
# NetworkTap Access Point Configuration
interface=${iface}
driver=nl80211

# SSID Configuration
ssid=${ssid}
hw_mode=g
channel=${channel}
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0

# WPA2 Security
wpa=2
wpa_passphrase=${passphrase}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP

# Performance
wmm_enabled=1
EOF
    
    chmod 600 /etc/hostapd/hostapd.conf
    
    # Update hostapd defaults
    sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd 2>/dev/null || true
    
    log "  SSID: $ssid"
    log "  Channel: $channel"
    log "  Security: WPA2-PSK"
}

create_dnsmasq_config() {
    local iface="$1"
    local subnet="${WIFI_AP_SUBNET:-192.168.42.0/24}"
    local ap_ip="${WIFI_AP_IP:-192.168.42.1}"
    
    # Extract network info
    local network=$(echo "$subnet" | cut -d/ -f1)
    local base=$(echo "$network" | cut -d. -f1-3)
    
    log "Creating dnsmasq configuration..."
    
    # Backup original config
    if [[ -f /etc/dnsmasq.conf ]] && [[ ! -f /etc/dnsmasq.conf.orig ]]; then
        cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
    fi
    
    cat > /etc/dnsmasq.d/networktap-ap.conf << EOF
# NetworkTap Access Point DHCP/DNS Configuration
interface=${iface}
bind-interfaces

# DHCP Range
dhcp-range=${base}.10,${base}.50,255.255.255.0,24h

# Gateway and DNS
dhcp-option=3,${ap_ip}
dhcp-option=6,${ap_ip}

# Domain
domain=networktap.local
local=/networktap.local/

# Logging
log-dhcp
log-queries
EOF
    
    log "  DHCP range: ${base}.10-${base}.50"
    log "  Gateway: ${ap_ip}"
}

configure_network_interface() {
    local iface="$1"
    local ap_ip="${WIFI_AP_IP:-192.168.42.1}"
    
    log "Configuring network interface..."
    
    # Create systemd-networkd config for AP
    cat > /etc/systemd/network/40-networktap-ap.network << EOF
[Match]
Name=${iface}

[Network]
Address=${ap_ip}/24
DHCPServer=no
IPForward=yes

[Link]
RequiredForOnline=no
EOF
    
    systemctl restart systemd-networkd || true
}

configure_firewall() {
    local iface="$1"
    local mgmt_iface="${NIC2:-eth1}"
    
    log "Configuring firewall for AP..."
    
    # Enable IP forwarding
    echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-networktap-ap.conf
    sysctl -p /etc/sysctl.d/99-networktap-ap.conf >/dev/null
    
    # Configure NAT (optional - allow AP clients to access internet via management interface)
    if [[ "${WIFI_AP_NAT_ENABLED:-yes}" == "yes" ]]; then
        iptables -t nat -A POSTROUTING -o "$mgmt_iface" -j MASQUERADE
        iptables -A FORWARD -i "$iface" -o "$mgmt_iface" -j ACCEPT
        iptables -A FORWARD -i "$mgmt_iface" -o "$iface" -m state --state RELATED,ESTABLISHED -j ACCEPT
        
        # Save iptables rules
        if command -v netfilter-persistent &>/dev/null; then
            netfilter-persistent save
        elif command -v iptables-save &>/dev/null; then
            iptables-save > /etc/iptables/rules.v4
        fi
        
        log "  NAT enabled"
    fi
}

create_systemd_service() {
    log "Creating systemd service..."
    
    cat > /etc/systemd/system/networktap-ap.service << 'EOF'
[Unit]
Description=NetworkTap WiFi Access Point
After=network.target systemd-networkd.service
Wants=hostapd.service dnsmasq.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/networktap/scripts/ap.sh start
ExecStop=/opt/networktap/scripts/ap.sh stop
TimeoutStartSec=30
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
}

main() {
    check_root
    
    log "=================================="
    log "NetworkTap Access Point Setup"
    log "=================================="
    
    # Detect WiFi interface
    WIFI_IFACE=$(detect_wifi_interface)
    log "WiFi interface: $WIFI_IFACE"
    
    # Check capabilities
    check_wifi_capability "$WIFI_IFACE"
    
    # Install packages
    install_packages
    
    # Create configurations
    create_hostapd_config "$WIFI_IFACE"
    create_dnsmasq_config "$WIFI_IFACE"
    configure_network_interface "$WIFI_IFACE"
    configure_firewall "$WIFI_IFACE"
    create_systemd_service
    
    # Update config file
    if ! grep -q "WIFI_AP_ENABLED" /etc/networktap.conf 2>/dev/null; then
        cat >> /etc/networktap.conf << EOF

# ── WiFi Access Point ────────────────────────────────────────
WIFI_AP_ENABLED=no
WIFI_AP_SSID=NetworkTap-Admin
WIFI_AP_PASSPHRASE=networktap123
WIFI_AP_CHANNEL=11
WIFI_AP_SUBNET=192.168.42.0/24
WIFI_AP_IP=192.168.42.1
WIFI_AP_NAT_ENABLED=yes
EOF
    fi
    
    log "=================================="
    log "Access Point setup complete!"
    log "=================================="
    log ""
    log "Configuration:"
    log "  SSID: ${WIFI_AP_SSID:-NetworkTap-Admin}"
    log "  Password: ${WIFI_AP_PASSPHRASE:-networktap123}"
    log "  Channel: ${WIFI_AP_CHANNEL:-11}"
    log "  AP IP: ${WIFI_AP_IP:-192.168.42.1}"
    log ""
    log "⚠️  IMPORTANT: Change the default password!"
    log ""
    log "To enable the AP:"
    log "  sudo /opt/networktap/scripts/ap.sh start"
    log ""
    log "Or configure in networktap.conf and:"
    log "  sudo systemctl enable --now networktap-ap"
}

main "$@"
