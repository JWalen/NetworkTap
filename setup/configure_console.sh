#!/usr/bin/env bash
# Configure console to show NetworkTap professional status screen
set -euo pipefail

echo "[+] Configuring console status display..."

# Install dialog if not present (for TUI)
if ! command -v dialog &>/dev/null; then
    echo "[+] Installing dialog for console UI..."
    apt-get update -qq && apt-get install -y -qq dialog
fi

# Mask the default getty on tty1 so it can't start
echo "[+] Disabling default getty on tty1..."
systemctl stop getty@tty1.service 2>/dev/null || true
systemctl disable getty@tty1.service 2>/dev/null || true
systemctl mask getty@tty1.service 2>/dev/null || true

# Enable our console status service
echo "[+] Enabling NetworkTap console service..."
systemctl unmask networktap-console.service 2>/dev/null || true
systemctl enable networktap-console.service

# Also update /etc/issue as fallback for serial consoles
mkdir -p /etc/systemd/system/serial-getty@.service.d
cat > /etc/systemd/system/serial-getty@.service.d/networktap.conf << 'EOF'
[Service]
ExecStartPre=-/opt/networktap/scripts/update_issue.sh
EOF

# Generate initial /etc/issue for serial consoles
/opt/networktap/scripts/update_issue.sh 2>/dev/null || true

# Reload systemd and start the console
systemctl daemon-reload
systemctl start networktap-console.service 2>/dev/null || true

echo "[+] Console status display configured"
echo "[i] TTY1 will show professional status screen"
echo "[i] Press 'Login' button to access shell"
