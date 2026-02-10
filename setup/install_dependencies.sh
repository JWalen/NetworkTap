#!/usr/bin/env bash
# Install system packages and Python dependencies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Detect distro
DISTRO=""
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="$ID"
fi
echo "[i] Detected distro: ${DISTRO:-unknown}"

echo "[+] Updating package lists..."
apt-get update -qq

echo "[+] Installing core packages..."
# Pre-configure tshark to allow non-root capture
echo "wireshark-common wireshark-common/install-setuid boolean true" | debconf-set-selections 2>/dev/null || true

apt-get install -y -qq \
    tcpdump \
    tshark \
    bridge-utils \
    ethtool \
    net-tools \
    iproute2 \
    ufw \
    python3 \
    python3-pip \
    python3-venv \
    gzip \
    curl \
    jq \
    lsb-release \
    gnupg2 \
    dialog

# ── Clean up stale third-party repos from prior runs ────
rm -f /etc/apt/sources.list.d/suricata.list
rm -f /usr/share/keyrings/suricata-archive-keyring.gpg

# ── Suricata ────────────────────────────────────────────
if ! command -v suricata &>/dev/null; then
    echo "[+] Installing Suricata..."

    if [[ "$DISTRO" == "ubuntu" ]]; then
        # Ubuntu: use the OISF PPA (not needed on Debian -- suricata is in repos)
        apt-get install -y -qq software-properties-common 2>/dev/null || true
        add-apt-repository -y ppa:oisf/suricata-stable 2>/dev/null || true
        apt-get update -qq
    fi

    # Install from distro repos (Debian trixie/bookworm ship suricata)
    apt-get install -y -qq suricata 2>/dev/null || {
        echo "[!] Could not install Suricata. Install manually if needed."
    }

    if command -v suricata &>/dev/null; then
        echo "[+] Updating Suricata rules..."
        suricata-update 2>/dev/null || true
    fi
else
    echo "[i] Suricata already installed: $(suricata -V 2>/dev/null || echo 'unknown version')"
fi

# ── Zeek ────────────────────────────────────────────────
if ! command -v zeek &>/dev/null; then
    echo "[+] Installing Zeek..."

    if [[ "$DISTRO" == "debian" ]]; then
        DEBIAN_VERSION="$(lsb_release -rs 2>/dev/null || echo '12')"
        # Use the openSUSE Build Service Debian repo
        echo "deb [signed-by=/usr/share/keyrings/zeek-archive-keyring.gpg] http://download.opensuse.org/repositories/security:/zeek/Debian_${DEBIAN_VERSION}/ /" \
            > /etc/apt/sources.list.d/zeek.list 2>/dev/null || true
        curl -fsSL "https://download.opensuse.org/repositories/security:zeek/Debian_${DEBIAN_VERSION}/Release.key" \
            | gpg --dearmor -o /usr/share/keyrings/zeek-archive-keyring.gpg 2>/dev/null || true
    elif [[ "$DISTRO" == "ubuntu" ]]; then
        UBUNTU_VERSION="$(lsb_release -rs 2>/dev/null || echo '22.04')"
        echo "deb [signed-by=/usr/share/keyrings/zeek-archive-keyring.gpg] http://download.opensuse.org/repositories/security:/zeek/xUbuntu_${UBUNTU_VERSION}/ /" \
            > /etc/apt/sources.list.d/zeek.list 2>/dev/null || true
        curl -fsSL "https://download.opensuse.org/repositories/security:zeek/xUbuntu_${UBUNTU_VERSION}/Release.key" \
            | gpg --dearmor -o /usr/share/keyrings/zeek-archive-keyring.gpg 2>/dev/null || true
    fi

    apt-get update -qq 2>/dev/null || true
    apt-get install -y -qq zeek 2>/dev/null \
        || apt-get install -y -qq zeek-lts 2>/dev/null \
        || {
            echo "[!] Could not install Zeek from repository."
            # Clean up failed repo
            rm -f /etc/apt/sources.list.d/zeek.list
            apt-get update -qq 2>/dev/null || true
            echo "[!] Try installing Zeek manually: https://docs.zeek.org/en/master/install.html"
        }
else
    echo "[i] Zeek already installed: $(zeek --version 2>/dev/null || echo 'unknown version')"
fi

# Add zeek to PATH if installed but not in PATH
for zeek_bin in /opt/zeek/bin /usr/local/zeek/bin; do
    if [[ -x "${zeek_bin}/zeek" ]] && ! command -v zeek &>/dev/null; then
        echo "export PATH=\$PATH:${zeek_bin}" > /etc/profile.d/zeek.sh
        export PATH="$PATH:${zeek_bin}"
        echo "[+] Added ${zeek_bin} to PATH"
        break
    fi
done

# ── Python Virtual Environment ──────────────────────────
echo "[+] Setting up Python virtual environment..."
VENV_DIR="/opt/networktap/venv"
python3 -m venv "$VENV_DIR"
source "${VENV_DIR}/bin/activate"

echo "[+] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "${PROJECT_DIR}/web/requirements.txt"

deactivate

# ── Verify critical tools ────────────────────────────────
echo "[+] Verifying installations..."
for cmd in tcpdump tshark suricata zeek python3; do
    if command -v "$cmd" &>/dev/null; then
        echo "[i] $cmd: $(command -v $cmd)"
    else
        echo "[!] $cmd: NOT FOUND"
    fi
done

echo "[+] Dependencies installed successfully"
