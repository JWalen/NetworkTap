#!/usr/bin/env bash
# Configure Zeek IDS for NetworkTap
set -euo pipefail

source /etc/networktap.conf

if [[ "$ZEEK_ENABLED" != "yes" ]]; then
    echo "[i] Zeek disabled in config, skipping"
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check PATH and known install locations
ZEEK_BIN=""
if command -v zeek &>/dev/null; then
    ZEEK_BIN="$(command -v zeek)"
else
    for candidate in /opt/zeek/bin/zeek /usr/local/zeek/bin/zeek /usr/bin/zeek; do
        if [[ -x "$candidate" ]]; then
            ZEEK_BIN="$candidate"
            break
        fi
    done
fi

# Install Zeek if not found
if [[ -z "$ZEEK_BIN" ]]; then
    echo "[+] Zeek not found, attempting to install..."
    
    # Detect OS
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS_ID="${ID:-unknown}"
        OS_VERSION="${VERSION_ID:-unknown}"
    else
        OS_ID="unknown"
        OS_VERSION="unknown"
    fi
    
    case "$OS_ID" in
        ubuntu|debian)
            # Add Zeek repository
            echo "[+] Adding Zeek repository for ${OS_ID} ${OS_VERSION}..."
            apt-get install -y curl gnupg
            
            if [[ "$OS_ID" == "ubuntu" ]]; then
                REPO_URL="https://download.opensuse.org/repositories/security:/zeek/xUbuntu_${OS_VERSION}/"
            else
                REPO_URL="https://download.opensuse.org/repositories/security:/zeek/Debian_${OS_VERSION}/"
            fi
            
            echo "deb ${REPO_URL} /" > /etc/apt/sources.list.d/zeek.list
            curl -fsSL "${REPO_URL}Release.key" | gpg --dearmor > /etc/apt/trusted.gpg.d/zeek.gpg
            
            apt-get update
            apt-get install -y zeek || apt-get install -y zeek-lts || {
                echo "[!] Failed to install Zeek from repository"
                exit 1
            }
            ;;
        *)
            echo "[!] Unsupported OS: ${OS_ID}. Please install Zeek manually."
            exit 1
            ;;
    esac
    
    # Find Zeek after install
    for candidate in /opt/zeek/bin/zeek /usr/local/zeek/bin/zeek /usr/bin/zeek; do
        if [[ -x "$candidate" ]]; then
            ZEEK_BIN="$candidate"
            break
        fi
    done
    
    if [[ -z "$ZEEK_BIN" ]]; then
        echo "[!] Zeek installation failed - binary not found"
        exit 1
    fi
fi

echo "[i] Found Zeek at: ${ZEEK_BIN}"
ZEEK_DIR_BIN="$(dirname "$ZEEK_BIN")"

# Add Zeek to system PATH if not already
if [[ ! -f /etc/profile.d/zeek.sh ]]; then
    echo "export PATH=${ZEEK_DIR_BIN}:\$PATH" > /etc/profile.d/zeek.sh
    echo "[+] Added Zeek to system PATH"
fi

# Determine capture interface - never use "auto"
CAPTURE_IF="$NIC1"
if [[ "$MODE" == "bridge" ]]; then
    CAPTURE_IF="$BRIDGE_NAME"
fi
if [[ -n "${ZEEK_IFACE:-}" ]] && [[ "$ZEEK_IFACE" != "auto" ]]; then
    CAPTURE_IF="$ZEEK_IFACE"
fi

# Validate interface exists
if ! ip link show "$CAPTURE_IF" &>/dev/null; then
    echo "[!] Warning: Interface $CAPTURE_IF does not exist"
    echo "[i] Available interfaces:"
    ip -brief link show | grep -v "^lo " || true
fi

echo "[+] Configuring Zeek on interface: ${CAPTURE_IF}"

# Update config if ZEEK_IFACE was "auto"
if grep -q "ZEEK_IFACE=auto" /etc/networktap.conf; then
    sed -i "s/ZEEK_IFACE=auto/ZEEK_IFACE=${CAPTURE_IF}/" /etc/networktap.conf
    echo "[+] Updated ZEEK_IFACE to ${CAPTURE_IF} in config"
fi

# Always create /etc/zeek directory
mkdir -p /etc/zeek
echo "[+] Ensured /etc/zeek directory exists"

# Note: We do NOT deploy a custom local.zeek anymore.
# The service runs Zeek from its installation directory and uses Zeek's
# built-in "local" script. JSON logging is configured via command line args.
echo "[i] Using Zeek's built-in local script (JSON output enabled via service)"

# Configure node.cfg if Zeek etc directory exists
for etc_dir in /opt/zeek/etc /usr/local/zeek/etc /etc/zeek; do
    if [[ -d "$etc_dir" ]] || [[ "$etc_dir" == "/etc/zeek" ]]; then
        mkdir -p "$etc_dir"
        cat > "${etc_dir}/node.cfg" <<EOF
[zeek]
type=standalone
host=localhost
interface=${CAPTURE_IF}
EOF
        echo "[+] Created node.cfg in ${etc_dir}/"
        break
    fi
done

# Create log directory with proper permissions
mkdir -p "$ZEEK_LOG_DIR"
chmod 755 "$ZEEK_LOG_DIR"
echo "[+] Created log directory: ${ZEEK_LOG_DIR}"

# Create networktap log directory
mkdir -p /var/log/networktap
chmod 755 /var/log/networktap

# Make start script executable
chmod +x /opt/networktap/scripts/start_zeek.sh 2>/dev/null || true

# Test that Zeek can start (quick syntax check)
echo "[i] Testing Zeek..."
if $ZEEK_BIN --help &>/dev/null; then
    echo "[+] Zeek binary is functional"
else
    echo "[!] Warning: Zeek binary test failed"
fi

echo "[+] Zeek configuration complete"
