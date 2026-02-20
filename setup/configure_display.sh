#!/usr/bin/env bash
# Configure FR202 front panel display (ST7789V 3.5" 320x240 TFT on SPI3)
# Backlight via I2C expander at 0x3C on I2C bus 1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/networktap"

echo "[+] Configuring FR202 front panel display..."

# ── Step 1: Ensure required overlays are in config.txt ──
CONFIG_TXT=""
for f in /boot/firmware/config.txt /boot/config.txt; do
    [[ -f "$f" ]] && CONFIG_TXT="$f" && break
done

if [[ -z "$CONFIG_TXT" ]]; then
    echo "[!] Could not find config.txt — skipping display setup"
    exit 0
fi

NEEDS_REBOOT=false

# Disable generic SPI — FR202 uses specific SPI3/SPI4 overlays instead
# Per OnLogic docs: dtparam=spi=on must be commented out for display to work
if grep -q "^dtparam=spi=on" "$CONFIG_TXT"; then
    echo "[+] Disabling generic SPI in $CONFIG_TXT (FR202 uses SPI3/SPI4 overlays)..."
    sed -i 's/^dtparam=spi=on/#dtparam=spi=on/' "$CONFIG_TXT"
    NEEDS_REBOOT=true
fi

# Enable I2C if commented out (needed for backlight on bus 1)
if grep -q "^#dtparam=i2c_arm=on" "$CONFIG_TXT"; then
    echo "[+] Enabling I2C in $CONFIG_TXT..."
    sed -i 's/^#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' "$CONFIG_TXT"
    NEEDS_REBOOT=true
elif ! grep -q "^dtparam=i2c_arm=on" "$CONFIG_TXT"; then
    echo "[+] Adding I2C enable to $CONFIG_TXT..."
    echo "dtparam=i2c_arm=on" >> "$CONFIG_TXT"
    NEEDS_REBOOT=true
fi

# I2C1 on pins 44/45 (default pins 2/3 conflict with SPI0 on CM4)
if ! grep -q "dtoverlay=i2c1,pins_44_45" "$CONFIG_TXT"; then
    echo "[+] Adding I2C1 overlay on pins 44/45 (avoids SPI0 conflict)..."
    # Add before [cm4] section if it exists, otherwise append
    if grep -q "^\[cm4\]" "$CONFIG_TXT"; then
        sed -i '/^\[cm4\]/i dtoverlay=i2c1,pins_44_45' "$CONFIG_TXT"
    else
        echo "dtoverlay=i2c1,pins_44_45" >> "$CONFIG_TXT"
    fi
    NEEDS_REBOOT=true
fi

# Add FR202-specific SPI3 overlay for the display
if ! grep -q "dtoverlay=spi3-1cs" "$CONFIG_TXT"; then
    echo "[+] Adding SPI3 overlay for FR202 display..."
    cat >> "$CONFIG_TXT" << 'EOF'

# FR202 front panel display (ST7789V on SPI3)
dtoverlay=spi3-1cs,cs0_pin=24
EOF
    NEEDS_REBOOT=true
fi

# Add SPI4 overlay (for ADC, also needed for FR202 daughterboard)
if ! grep -q "dtoverlay=spi4-1cs" "$CONFIG_TXT"; then
    echo "[+] Adding SPI4 overlay for FR202 daughterboard..."
    echo "dtoverlay=spi4-1cs" >> "$CONFIG_TXT"
    NEEDS_REBOOT=true
fi

# Add I2C5 overlay (for mux and other FR202 peripherals)
if ! grep -q "dtoverlay=i2c5" "$CONFIG_TXT"; then
    echo "[+] Adding I2C5 overlay for FR202 peripherals..."
    echo "dtoverlay=i2c5,pins12_13=on,baudrate=40000" >> "$CONFIG_TXT"
    NEEDS_REBOOT=true
fi

# ── Step 2: Ensure i2c-dev module loads at boot ──
if [[ ! -f /etc/modules-load.d/i2c-dev.conf ]] || ! grep -q "i2c-dev" /etc/modules-load.d/i2c-dev.conf 2>/dev/null; then
    echo "[+] Configuring i2c-dev module to load at boot..."
    echo "i2c-dev" > /etc/modules-load.d/i2c-dev.conf
fi

# Load it now if not already loaded
modprobe i2c-dev 2>/dev/null || true

# ── Step 3: Install i2c-tools for backlight control ──
if ! command -v i2cset &>/dev/null; then
    echo "[+] Installing i2c-tools..."
    apt-get install -y -qq i2c-tools 2>/dev/null || true
fi

# ── Step 4: Install Python dependencies ──
echo "[+] Installing display dependencies..."
if [[ -d "$INSTALL_DIR/venv" ]]; then
    source "$INSTALL_DIR/venv/bin/activate"
    pip install --quiet pillow st7789 spidev RPi.GPIO smbus2 gpiod gpiodevice 2>/dev/null || true
    deactivate
elif [[ -d "$INSTALL_DIR/web/venv" ]]; then
    source "$INSTALL_DIR/web/venv/bin/activate"
    pip install --quiet pillow st7789 spidev RPi.GPIO smbus2 gpiod gpiodevice 2>/dev/null || true
    deactivate
else
    pip3 install --quiet pillow st7789 spidev RPi.GPIO smbus2 gpiod gpiodevice 2>/dev/null || true
fi

# Install fonts if not present
if ! dpkg -l fonts-dejavu-core &>/dev/null 2>&1; then
    echo "[+] Installing fonts..."
    apt-get install -y -qq fonts-dejavu-core 2>/dev/null || true
fi

# ── Step 5: Enable the display service ──
echo "[+] Enabling display service..."
systemctl enable networktap-display.service 2>/dev/null || true

# Only start if SPI device exists (otherwise needs reboot first)
if ls /dev/spidev3.* &>/dev/null; then
    echo "[+] SPI3 detected — starting display service..."
    systemctl start networktap-display.service 2>/dev/null || true
elif [[ "$NEEDS_REBOOT" == "true" ]]; then
    echo "[!] SPI3 overlay added but requires reboot to take effect"
    echo "[i] The display service will start automatically after reboot"
else
    echo "[!] SPI3 device not found — display service enabled but not started"
fi

if [[ "$NEEDS_REBOOT" == "true" ]]; then
    echo "[!] REBOOT REQUIRED for display overlays to take effect"
fi

echo "[+] FR202 front panel display configured"
