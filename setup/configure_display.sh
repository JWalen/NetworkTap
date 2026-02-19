#!/usr/bin/env bash
# Configure FR202 front panel display (ST7789 2.4" 320x240 TFT)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "[+] Configuring FR202 front panel display..."

# Check if SPI is available (FR202 exposes ST7789 on SPI)
if [[ ! -d /dev/spidev* ]] 2>/dev/null && [[ ! -e /dev/spidev0.0 ]]; then
    echo "[!] SPI device not found — skipping display setup"
    echo "[i] If this is an FR202, ensure SPI is enabled in BIOS/device tree"
    exit 0
fi

# Install Python dependencies for the display
echo "[+] Installing display dependencies..."
if [[ -d "${PROJECT_DIR}/web/venv" ]]; then
    source "${PROJECT_DIR}/web/venv/bin/activate"
    pip install --quiet pillow st7789 spidev
    deactivate
else
    pip3 install --quiet pillow st7789 spidev
fi

# Install fonts if not present
if ! dpkg -l fonts-dejavu-core &>/dev/null 2>&1; then
    echo "[+] Installing fonts..."
    apt-get install -y -qq fonts-dejavu-core
fi

# Enable and start the display service
echo "[+] Enabling display service..."
systemctl enable networktap-display.service
systemctl start networktap-display.service

echo "[+] Front panel display configured"
echo "[i] Display refreshes every 5 seconds with system status"
