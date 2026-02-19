#!/usr/bin/env bash
# NetworkTap Console Status Screen
# Professional TUI display using dialog

export TERM=linux
export NCURSES_NO_UTF8_ACS=1
export LC_ALL=C.UTF-8 2>/dev/null || export LC_ALL=C

# Wait for system to be ready
sleep 2

# Check for dialog
if ! command -v dialog &>/dev/null; then
    echo "Dialog not found, falling back to login..."
    sleep 3
    exec /sbin/agetty --noclear tty1 linux
fi

# Clear any existing screen content
clear

show_status() {
    source /etc/networktap.conf 2>/dev/null || true

    # Get management interface and IP
    if [[ "${MODE:-span}" == "bridge" ]]; then
        MGMT_IFACE="${BRIDGE_NAME:-br0}"
    else
        MGMT_IFACE="${NIC2:-eth1}"
    fi

    # Get IP address
    MGMT_IP=$(ip -4 addr show "$MGMT_IFACE" 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1)
    [[ -z "$MGMT_IP" ]] && MGMT_IP="Acquiring..."

    # Get gateway
    GATEWAY=$(ip route | grep default | grep "$MGMT_IFACE" | awk '{print $3}' | head -1)
    [[ -z "$GATEWAY" ]] && GATEWAY="--"

    # System info
    HOSTNAME=$(hostname)
    UPTIME=$(uptime -p 2>/dev/null | sed 's/up //')
    KERNEL=$(uname -r)
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d. -f1)%
    MEM_INFO=$(free -m | awk 'NR==2{printf "%sMB / %sMB (%.0f%%)", $3, $2, $3*100/$2}')

    # Disk info
    DISK_INFO=$(df -h "${CAPTURE_DIR:-/var/lib/networktap/captures}" 2>/dev/null | awk 'NR==2{printf "%s / %s (%s)", $3, $2, $5}')
    [[ -z "$DISK_INFO" ]] && DISK_INFO="--"

    # PCAP count
    PCAP_COUNT=$(find "${CAPTURE_DIR:-/var/lib/networktap/captures}" -name "*.pcap*" 2>/dev/null | wc -l)

    # Service status
    check_svc() {
        if systemctl is-active --quiet "$1" 2>/dev/null; then
            echo "[ RUNNING ]"
        else
            echo "[ STOPPED ]"
        fi
    }

    WEB_STATUS=$(check_svc networktap-web)
    CAP_STATUS=$(check_svc networktap-capture)
    SURI_STATUS=$(check_svc networktap-suricata)
    ZEEK_STATUS=$(check_svc networktap-zeek)

    # Version
    APP_VERSION=$(cat /opt/networktap/VERSION 2>/dev/null || echo "unknown")

    # Current time
    CURRENT_TIME=$(date '+%Y-%m-%d %H:%M:%S')

    # Helper function to pad strings for alignment
    pad() {
        local str="$1"
        local len="$2"
        printf "%-${len}s" "${str:0:$len}"
    }

    # Center a line within width 85
    center() {
        local str="$1"
        local width=85
        local len=${#str}
        local pad=$(( (width - len) / 2 ))
        printf "%*s%s" $pad "" "$str"
    }

    # Build the status message - centered within dialog
    STATUS_MSG="
$(center "███╗   ██╗███████╗████████╗██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗████████╗ █████╗ ██████╗")
$(center "████╗  ██║██╔════╝╚══██╔══╝██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝╚══██╔══╝██╔══██╗██╔══██╗")
$(center "██╔██╗ ██║█████╗     ██║   ██║ █╗ ██║██║   ██║██████╔╝█████╔╝    ██║   ███████║██████╔╝")
$(center "██║╚██╗██║██╔══╝     ██║   ██║███╗██║██║   ██║██╔══██╗██╔═██╗    ██║   ██╔══██║██╔═══╝")
$(center "██║ ╚████║███████╗   ██║   ╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗   ██║   ██║  ██║██║")
$(center "╚═╝  ╚═══╝╚══════╝   ╚═╝    ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝")

$(center "Network Monitoring Appliance  v${APP_VERSION}")

$(center "═══════════════════════════════════════════════════════════════════════════════════")

   SYSTEM                                    NETWORK
   ──────────────────────────────────────    ──────────────────────────────────────
   Hostname     $(pad "$HOSTNAME" 25)    Mode         $(pad "${MODE:-span}" 25)
   Kernel       $(pad "$KERNEL" 25)    Interface    $(pad "$MGMT_IFACE" 25)
   Uptime       $(pad "$UPTIME" 25)    IP Address   $(pad "$MGMT_IP" 25)
   CPU Usage    $(pad "$CPU_USAGE" 25)    Gateway      $(pad "$GATEWAY" 25)
   Memory       $(pad "$MEM_INFO" 25)    Web Port     $(pad "${WEB_PORT:-8443}" 25)

$(center "═══════════════════════════════════════════════════════════════════════════════════")

   SERVICES                                  STORAGE
   ──────────────────────────────────────    ──────────────────────────────────────
   Web UI       $(pad "$WEB_STATUS" 25)    Disk Usage   $(pad "$DISK_INFO" 25)
   Capture      $(pad "$CAP_STATUS" 25)    PCAP Files   $(pad "$PCAP_COUNT files" 25)
   Suricata     $(pad "$SURI_STATUS" 25)    Retention    $(pad "${RETENTION_DAYS:-7} days" 25)
   Zeek         $(pad "$ZEEK_STATUS" 25)

$(center "═══════════════════════════════════════════════════════════════════════════════════")

   ACCESS
   ──────────────────────────────────────────────────────────────────────────────────────
   Web UI       http://${MGMT_IP}:${WEB_PORT:-8443}
   SSH          ssh root@${MGMT_IP}

$(center "═══════════════════════════════════════════════════════════════════════════════════")

$(center "Last updated: ${CURRENT_TIME}")
"

    # Get terminal size
    TERM_ROWS=$(tput lines 2>/dev/null || echo 24)
    TERM_COLS=$(tput cols 2>/dev/null || echo 80)

    # Calculate dialog size (leave some padding)
    DLG_HEIGHT=$((TERM_ROWS - 2))
    DLG_WIDTH=$((TERM_COLS - 4))

    # Minimum sizes
    [[ $DLG_HEIGHT -lt 30 ]] && DLG_HEIGHT=30
    [[ $DLG_WIDTH -lt 90 ]] && DLG_WIDTH=90

    # Display using dialog centered on screen
    dialog --no-collapse \
           --colors \
           --title " NetworkTap Status " \
           --ok-label "Login" \
           --extra-button --extra-label "Refresh" \
           --msgbox "$STATUS_MSG" $DLG_HEIGHT $DLG_WIDTH

    return $?
}

# Main loop
while true; do
    clear
    show_status
    EXIT_CODE=$?

    if [[ $EXIT_CODE -eq 0 ]]; then
        # User pressed "Login" (OK)
        clear
        exec /sbin/agetty --noclear tty1 linux
    elif [[ $EXIT_CODE -eq 3 ]]; then
        # User pressed "Refresh" (Extra button)
        continue
    else
        # Escape or other - refresh after delay
        sleep 5
    fi
done
