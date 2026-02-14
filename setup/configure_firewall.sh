#!/usr/bin/env bash
# Configure UFW firewall for NetworkTap
set -euo pipefail

source /etc/networktap.conf

echo "[+] Configuring firewall..."

# Determine management interface
MGMT_IFACE="$NIC2"
if [[ "$MODE" == "bridge" ]]; then
    MGMT_IFACE="$BRIDGE_NAME"
fi

# Reset UFW to defaults
ufw --force reset

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH on management interface
ufw allow in on "$MGMT_IFACE" to any port 22 proto tcp comment "NetworkTap SSH"

# Allow web dashboard on management interface
ufw allow in on "$MGMT_IFACE" to any port "$WEB_PORT" proto tcp comment "NetworkTap Web UI"

# In bridge mode, allow forwarding
if [[ "$MODE" == "bridge" ]]; then
    # Enable IP forwarding for bridge
    sysctl -w net.ipv4.ip_forward=1
    if ! grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf 2>/dev/null; then
        echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    fi

    # CRITICAL: Disable bridge netfilter so iptables/nftables don't
    # intercept Layer 2 bridged frames. Without this, UFW's default
    # deny policy drops all traffic passing through the bridge.
    modprobe br_netfilter 2>/dev/null || true
    sysctl -w net.bridge.bridge-nf-call-iptables=0
    sysctl -w net.bridge.bridge-nf-call-ip6tables=0
    sysctl -w net.bridge.bridge-nf-call-arptables=0

    # Make persistent
    cat > /etc/sysctl.d/90-networktap-bridge.conf <<EOF
net.bridge.bridge-nf-call-iptables=0
net.bridge.bridge-nf-call-ip6tables=0
net.bridge.bridge-nf-call-arptables=0
net.ipv4.ip_forward=1
EOF

    # Also set UFW forward policy to accept for bridged traffic
    ufw default allow routed

    # Allow traffic on the bridge interface itself (for management)
    ufw allow in on "$BRIDGE_NAME" comment "NetworkTap Bridge Management"
else
    # SPAN mode: remove bridge sysctl overrides if present
    rm -f /etc/sysctl.d/90-networktap-bridge.conf
fi

# Enable UFW
ufw --force enable

echo "[+] Firewall rules applied:"
ufw status verbose

echo "[+] Firewall configuration complete"
