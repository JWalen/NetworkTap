#!/usr/bin/env bash
# WiFi management for NetworkTap
set -euo pipefail

IFACE="${WIFI_IFACE:-wlan0}"
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant-${IFACE}.conf"

usage() {
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  scan                 Scan for available networks"
    echo "  connect <SSID> <PSK> Connect to a WPA2 network"
    echo "  disconnect           Disconnect from WiFi"
    echo "  status               Show connection status"
    echo "  forget               Remove saved network and disconnect"
    echo ""
    exit 1
}

ensure_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "[!] Must be run as root"
        exit 1
    fi
}

ensure_iface() {
    if ! ip link show "$IFACE" &>/dev/null; then
        echo "[!] WiFi interface ${IFACE} not found"
        exit 1
    fi
}

install_deps() {
    if ! command -v wpa_supplicant &>/dev/null; then
        echo "[+] Installing wpa_supplicant..."
        apt-get update -qq
        apt-get install -y -qq wpasupplicant
    fi
}

do_scan() {
    ensure_iface
    ip link set "$IFACE" up 2>/dev/null || true
    echo "[+] Scanning on ${IFACE}..."

    # Use iw if available, fall back to wpa_cli
    if command -v iw &>/dev/null; then
        iw dev "$IFACE" scan 2>/dev/null | awk '
            /^BSS / {
                if (ssid != "") printf "%s\t%s\t%s\t%s\n", ssid, signal, freq, security
                mac=$2; ssid=""; signal=""; freq=""; security="Open"
            }
            /SSID:/ { ssid=substr($0, index($0, "SSID: ")+6) }
            /signal:/ { signal=$2+0 }
            /freq:/ { freq=$2+0 }
            /RSN:/ { security="WPA2" }
            /WPA:/ { if (security=="") security="WPA" }
            /capability:.*Privacy/ { if (security=="") security="WEP" }
            END {
                if (ssid != "") printf "%s\t%s\t%s\t%s\n", ssid, signal, freq, security
            }
        ' | sort -t'	' -k1,1 -u
    else
        echo "[!] Install iw for scan support: apt install iw"
    fi
}

do_connect() {
    local ssid="$1"
    local psk="$2"

    ensure_root
    ensure_iface
    install_deps

    echo "[+] Connecting to '${ssid}' on ${IFACE}..."

    # Create wpa_supplicant config
    mkdir -p /etc/wpa_supplicant
    wpa_passphrase "$ssid" "$psk" > "$WPA_CONF"
    chmod 600 "$WPA_CONF"

    # Create systemd-networkd config for WiFi
    cat > "/etc/systemd/network/30-networktap-wifi.network" <<EOF
[Match]
Name=${IFACE}

[Network]
DHCP=yes

[DHCP]
UseDNS=yes
UseNTP=yes
RouteMetric=600
EOF

    # Enable and start wpa_supplicant for this interface
    systemctl enable "wpa_supplicant@${IFACE}.service" 2>/dev/null || true
    systemctl restart "wpa_supplicant@${IFACE}.service"
    systemctl restart systemd-networkd

    # Wait for connection
    echo "[+] Waiting for connection..."
    for i in $(seq 1 30); do
        if ip -4 addr show "$IFACE" | grep -q "inet "; then
            echo "[+] Connected!"
            do_status
            return 0
        fi
        sleep 1
    done

    echo "[!] Connection timeout - check credentials or signal"
    do_status
    return 1
}

do_disconnect() {
    ensure_root

    echo "[+] Disconnecting WiFi..."
    systemctl stop "wpa_supplicant@${IFACE}.service" 2>/dev/null || true
    ip link set "$IFACE" down 2>/dev/null || true
    echo "[+] Disconnected"
}

do_forget() {
    ensure_root

    do_disconnect
    rm -f "$WPA_CONF"
    rm -f "/etc/systemd/network/30-networktap-wifi.network"
    systemctl disable "wpa_supplicant@${IFACE}.service" 2>/dev/null || true
    systemctl restart systemd-networkd 2>/dev/null || true
    echo "[+] WiFi configuration removed"
}

do_status() {
    ensure_iface

    echo "Interface:  ${IFACE}"

    local state
    state=$(ip -br link show "$IFACE" 2>/dev/null | awk '{print $2}') || true
    echo "Link:       ${state:-UNKNOWN}"

    # Check if wpa_supplicant is running
    if systemctl is-active --quiet "wpa_supplicant@${IFACE}.service" 2>/dev/null; then
        echo "WPA:        active"
    else
        echo "WPA:        inactive"
    fi

    # Show connected SSID
    if command -v iw &>/dev/null; then
        local ssid
        ssid=$(iw dev "$IFACE" link 2>/dev/null | awk '/SSID:/{print $2}') || true
        if [[ -n "$ssid" ]]; then
            echo "SSID:       ${ssid}"
            local signal
            signal=$(iw dev "$IFACE" link 2>/dev/null | awk '/signal:/{print $2, $3}') || true
            echo "Signal:     ${signal}"
            local freq
            freq=$(iw dev "$IFACE" link 2>/dev/null | awk '/freq:/{print $2}') || true
            echo "Frequency:  ${freq} MHz"
        else
            echo "SSID:       (not connected)"
        fi
    fi

    # Show IP
    local ip
    ip=$(ip -4 addr show "$IFACE" 2>/dev/null | awk '/inet /{split($2,a,"/"); print a[1]}') || true
    echo "IP:         ${ip:-(none)}"
}

# ── Main ──
[[ $# -ge 1 ]] || usage

case "$1" in
    scan)       do_scan ;;
    connect)
        [[ $# -ge 3 ]] || { echo "[!] Usage: $0 connect <SSID> <PSK>"; exit 1; }
        do_connect "$2" "$3"
        ;;
    disconnect) do_disconnect ;;
    status)     do_status ;;
    forget)     do_forget ;;
    *)          usage ;;
esac
