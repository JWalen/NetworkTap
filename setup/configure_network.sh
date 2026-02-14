#!/usr/bin/env bash
# Configure network interfaces for SPAN or Bridge mode
set -euo pipefail

source /etc/networktap.conf

echo "[+] Configuring network for mode: ${MODE}"

# ── Ensure systemd-networkd is the active network manager ──────────
setup_network_manager() {
    echo "[+] Configuring systemd-networkd as network manager..."

    # Disable NetworkManager if present (it conflicts with systemd-networkd)
    if systemctl is-active --quiet NetworkManager 2>/dev/null; then
        echo "[+] Disabling NetworkManager (conflicts with systemd-networkd)..."
        systemctl stop NetworkManager 2>/dev/null || true
        systemctl disable NetworkManager 2>/dev/null || true
        systemctl mask NetworkManager 2>/dev/null || true
    fi

    # Disable other network managers that might interfere
    for svc in networking dhcpcd wicd connman; do
        if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
            echo "[+] Disabling $svc..."
            systemctl stop "$svc" 2>/dev/null || true
            systemctl disable "$svc" 2>/dev/null || true
        fi
    done

    # Enable systemd-networkd and systemd-resolved
    systemctl unmask systemd-networkd 2>/dev/null || true
    systemctl enable systemd-networkd
    systemctl enable systemd-resolved 2>/dev/null || true

    # Link resolv.conf to systemd-resolved if available
    if systemctl is-enabled --quiet systemd-resolved 2>/dev/null; then
        ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf 2>/dev/null || true
    fi

    echo "[+] systemd-networkd configured as network manager"
}

setup_network_manager

resolve_iface() {
    local iface="$1"
    if [[ "$iface" == "auto" ]]; then
        # Return the first physical NIC
        for i in /sys/class/net/*; do
            local name
            name="$(basename "$i")"
            [[ "$name" == "lo" ]] && continue
            [[ -d "/sys/class/net/${name}/device" ]] && echo "$name" && return
        done
    else
        echo "$iface"
    fi
}

configure_span_mode() {
    local capture_iface="$NIC1"
    local mgmt_iface="$NIC2"

    echo "[+] SPAN mode: ${capture_iface} = capture, ${mgmt_iface} = management"

    # Set capture interface to promiscuous mode
    ip link set "$capture_iface" promisc on
    ip link set "$capture_iface" up

    # Disable offloading on capture interface for accurate packet capture
    ethtool -K "$capture_iface" gro off gso off tso off lro off 2>/dev/null || true
    ethtool -K "$capture_iface" rx off tx off 2>/dev/null || true

    # Ensure management interface is up
    ip link set "$mgmt_iface" up

    # Create persistent configuration via systemd-networkd
    mkdir -p /etc/systemd/network

    # Capture interface - promiscuous, no IP
    cat > /etc/systemd/network/10-networktap-capture.network <<EOF
[Match]
Name=${capture_iface}

[Link]
Promiscuous=yes

[Network]
LinkLocalAddressing=no
LLDP=no
EmitLLDP=no
EOF

    # Management interface - DHCP or static
    if [[ "$MGMT_IP" == "dhcp" ]]; then
        cat > /etc/systemd/network/20-networktap-mgmt.network <<EOF
[Match]
Name=${mgmt_iface}

[Network]
DHCP=yes

[DHCP]
UseDNS=yes
UseNTP=yes
EOF
    else
        # Build static IP config - only include Gateway if set
        {
            echo "[Match]"
            echo "Name=${mgmt_iface}"
            echo ""
            echo "[Network]"
            echo "Address=${MGMT_IP}"
            [[ -n "${MGMT_GATEWAY:-}" ]] && echo "Gateway=${MGMT_GATEWAY}"
            echo "DNS=${MGMT_DNS:-8.8.8.8}"
        } > /etc/systemd/network/20-networktap-mgmt.network
    fi

    # Remove bridge config if switching from bridge mode
    ip link set "$BRIDGE_NAME" down 2>/dev/null || true
    ip link delete "$BRIDGE_NAME" type bridge 2>/dev/null || true
    rm -f /etc/systemd/network/10-networktap-bridge.netdev
    rm -f /etc/systemd/network/10-networktap-bridge.network
    rm -f /etc/systemd/network/10-networktap-bridge-member-*.network

    echo "[+] SPAN mode configured"
}

configure_bridge_mode() {
    echo "[+] Bridge mode: ${NIC1} + ${NIC2} -> ${BRIDGE_NAME}"

    # Disable offloading on both interfaces
    for iface in "$NIC1" "$NIC2"; do
        ip link set "$iface" up
        ip link set "$iface" promisc on
        ethtool -K "$iface" gro off gso off tso off lro off 2>/dev/null || true
    done

    mkdir -p /etc/systemd/network

    # Bridge device
    cat > /etc/systemd/network/10-networktap-bridge.netdev <<EOF
[NetDev]
Name=${BRIDGE_NAME}
Kind=bridge

[Bridge]
STP=no
ForwardDelaySec=0
EOF

    # Bridge member: NIC1
    cat > /etc/systemd/network/10-networktap-bridge-member-nic1.network <<EOF
[Match]
Name=${NIC1}

[Link]
Promiscuous=yes

[Network]
Bridge=${BRIDGE_NAME}
EOF

    # Bridge member: NIC2
    cat > /etc/systemd/network/10-networktap-bridge-member-nic2.network <<EOF
[Match]
Name=${NIC2}

[Link]
Promiscuous=yes

[Network]
Bridge=${BRIDGE_NAME}
EOF

    # Bridge network config (management via bridge IP)
    if [[ "$MGMT_IP" == "dhcp" ]]; then
        cat > /etc/systemd/network/10-networktap-bridge.network <<EOF
[Match]
Name=${BRIDGE_NAME}

[Network]
DHCP=yes

[DHCP]
UseDNS=yes
UseNTP=yes
EOF
    else
        # Build static IP config - only include Gateway if set
        {
            echo "[Match]"
            echo "Name=${BRIDGE_NAME}"
            echo ""
            echo "[Network]"
            echo "Address=${MGMT_IP}"
            [[ -n "${MGMT_GATEWAY:-}" ]] && echo "Gateway=${MGMT_GATEWAY}"
            echo "DNS=${MGMT_DNS:-8.8.8.8}"
        } > /etc/systemd/network/10-networktap-bridge.network
    fi

    # Remove SPAN-mode configs
    rm -f /etc/systemd/network/10-networktap-capture.network
    rm -f /etc/systemd/network/20-networktap-mgmt.network

    echo "[+] Bridge mode configured"
}

# Apply configuration
case "$MODE" in
    span)   configure_span_mode ;;
    bridge) configure_bridge_mode ;;
    *)
        echo "[!] Unknown mode: ${MODE}. Use 'span' or 'bridge'"
        exit 1
        ;;
esac

# Reload and restart systemd-networkd to apply changes
echo "[+] Applying network configuration..."
systemctl daemon-reload
systemctl restart systemd-networkd

# Wait for networkd to settle
sleep 2

# Verify systemd-networkd is running
if systemctl is-active --quiet systemd-networkd; then
    echo "[+] systemd-networkd is active"
else
    echo "[!] Warning: systemd-networkd may not be running correctly"
    systemctl status systemd-networkd --no-pager || true
fi

echo "[+] Network configuration complete"
