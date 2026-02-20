#!/usr/bin/env bash
# WiFi Monitor Mode & Packet Capture Management
# Enables wireless packet capture similar to wired capture

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="/etc/networktap.conf"
CAPTURE_DIR="/var/lib/networktap/wifi-captures"
PID_FILE="/var/run/networktap/wifi-capture.pid"

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

load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
    else
        error "Config file not found: $CONFIG_FILE"
    fi
}

detect_wifi_interface() {
    for iface in /sys/class/net/*; do
        iface_name=$(basename "$iface")
        if [[ -d "$iface/wireless" ]] || [[ -d "$iface/phy80211" ]]; then
            echo "$iface_name"
            return 0
        fi
    done
    return 1
}

check_monitor_support() {
    local iface="$1"

    if ! command -v iw &>/dev/null; then
        error "iw command not found. Install with: apt install iw"
    fi

    # Already in monitor mode
    if iw "$iface" info 2>/dev/null | grep -q "type monitor"; then
        return 0
    fi

    # Check if the phy supports monitor mode at all
    local phy=$(iw dev "$iface" info 2>/dev/null | grep -oP 'wiphy \K\d+')
    if [[ -n "$phy" ]]; then
        if ! iw phy "phy${phy}" info 2>/dev/null | grep -qP '^\s+\* monitor'; then
            local driver=$(basename "$(readlink -f "/sys/class/net/${iface}/device/driver")" 2>/dev/null || echo "unknown")
            error "Monitor mode not supported by $iface ($driver driver). The onboard WiFi chip does not support monitor mode. Use a USB WiFi adapter that supports monitor mode (e.g. Alfa AWUS036ACH, TP-Link TL-WN722N v1)."
        fi
    fi

    return 0
}

enable_monitor_mode() {
    local iface="$1"
    local channel="${WIFI_CAPTURE_CHANNEL:-11}"

    log "Enabling monitor mode on $iface..."

    # Kill ALL processes that might hold the interface
    # This must happen BEFORE bringing the interface down
    systemctl stop "wpa_supplicant@${iface}.service" 2>/dev/null || true
    systemctl stop wpa_supplicant 2>/dev/null || true
    systemctl stop NetworkManager 2>/dev/null || true
    killall -q wpa_supplicant dhclient dhcpcd 2>/dev/null || true
    if command -v airmon-ng &>/dev/null; then
        airmon-ng check kill >/dev/null 2>&1 || true
    fi

    # Wait for processes to release the interface
    sleep 2

    # Bring interface down
    ip link set "$iface" down 2>/dev/null || true
    sleep 1

    # Try iw first
    local monitor_err=""
    if command -v iw &>/dev/null; then
        monitor_err=$(iw dev "$iface" set type monitor 2>&1) && {
            log "  Monitor mode set via iw"
            MONITOR_IFACE="$iface"
        } || {
            log "  iw failed: $monitor_err"

            # Check for driver-level "not supported" — no fallback will help
            if echo "$monitor_err" | grep -qi "not supported\|EOPNOTSUPP\|(-95)"; then
                local driver=$(basename "$(readlink -f "/sys/class/net/${iface}/device/driver")" 2>/dev/null || echo "unknown")
                error "Monitor mode not supported by $iface ($driver driver). Use a USB WiFi adapter that supports monitor mode (e.g. Alfa AWUS036ACH, TP-Link TL-WN722N v1)."
            fi

            # Try airmon-ng as fallback
            if command -v airmon-ng &>/dev/null; then
                log "  Trying airmon-ng..."
                airmon_out=$(airmon-ng start "$iface" 2>&1) || true
                log "  airmon-ng: $airmon_out"
                # airmon-ng creates interfaces like wlan0mon
                if ip link show "${iface}mon" &>/dev/null; then
                    MONITOR_IFACE="${iface}mon"
                else
                    MONITOR_IFACE="$iface"
                fi
            else
                # Last resort: try iwconfig
                if command -v iwconfig &>/dev/null; then
                    log "  Trying iwconfig..."
                    iwconfig "$iface" mode monitor 2>/dev/null || {
                        error "Failed to enable monitor mode. Error: $monitor_err"
                    }
                    MONITOR_IFACE="$iface"
                else
                    error "Failed to enable monitor mode. Error: $monitor_err. Install airmon-ng (aircrack-ng) for better support."
                fi
            fi
        }
    else
        error "iw command not found. Install with: apt install iw"
    fi

    # Bring interface up
    ip link set "${MONITOR_IFACE:-$iface}" up || {
        error "Failed to bring ${MONITOR_IFACE:-$iface} up after setting monitor mode"
    }

    # Set channel
    if [[ -n "$channel" ]]; then
        log "  Setting channel $channel..."
        iw dev "${MONITOR_IFACE:-$iface}" set channel "$channel" 2>/dev/null || \
            log "  Warning: Failed to set channel $channel"
    fi

    # Verify monitor mode is actually active
    local iface_mode=$(iw dev "${MONITOR_IFACE:-$iface}" info 2>/dev/null | grep -oP 'type \K\w+')
    if [[ "$iface_mode" == "monitor" ]]; then
        log "  Monitor mode confirmed on ${MONITOR_IFACE:-$iface}"
    else
        log "  Warning: Interface reports type '$iface_mode' instead of 'monitor'"
    fi

    echo "${MONITOR_IFACE:-$iface}"
}

disable_monitor_mode() {
    local iface="$1"
    
    log "Disabling monitor mode on $iface..."
    
    # Bring interface down
    ip link set "$iface" down 2>/dev/null || true
    
    # Set managed mode
    if command -v iw &>/dev/null; then
        iw dev "$iface" set type managed 2>/dev/null || true
    fi
    
    # If airmon-ng was used, stop it
    if command -v airmon-ng &>/dev/null && [[ "$iface" == *"mon" ]]; then
        airmon-ng stop "$iface" >/dev/null 2>&1 || true
    fi
    
    # Restart networking services
    systemctl restart systemd-networkd 2>/dev/null || true
    systemctl start wpa_supplicant 2>/dev/null || true
    
    log "  Monitor mode disabled"
}

start_capture() {
    check_root
    load_config
    
    if [[ "${WIFI_CAPTURE_ENABLED:-no}" != "yes" ]]; then
        error "WiFi capture is disabled (WIFI_CAPTURE_ENABLED=no)"
    fi
    
    # Detect interface
    WIFI_IFACE=$(detect_wifi_interface) || error "No WiFi interface found"
    log "WiFi interface: $WIFI_IFACE"
    
    # Check if already running
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            error "WiFi capture already running (PID: $pid)"
        fi
    fi
    
    # Create capture directory
    mkdir -p "$CAPTURE_DIR"
    mkdir -p "$(dirname "$PID_FILE")"
    
    # Enable monitor mode
    check_monitor_support "$WIFI_IFACE"
    MONITOR_IFACE=$(enable_monitor_mode "$WIFI_IFACE")
    
    # Build tcpdump command
    local max_size="${WIFI_CAPTURE_MAX_SIZE_MB:-100}"
    local max_files="${WIFI_CAPTURE_MAX_FILES:-50}"
    local filter="${WIFI_CAPTURE_FILTER:-}"
    
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local capture_file="${CAPTURE_DIR}/wifi-${timestamp}.pcap"
    
    log "Starting WiFi packet capture..."
    log "  Interface: $MONITOR_IFACE (monitor mode)"
    log "  Output: $capture_file"
    log "  Max size: ${max_size}MB per file"
    log "  Max files: $max_files"
    
    local tcpdump_cmd=(
        tcpdump
        -i "$MONITOR_IFACE"
        -w "$capture_file"
        -C "$max_size"
        -W "$max_files"
        -Z root
        -n
    )
    
    if [[ -n "$filter" ]]; then
        tcpdump_cmd+=("$filter")
    fi
    
    # Start capture in background
    "${tcpdump_cmd[@]}" >/dev/null 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    echo "$MONITOR_IFACE" > "$(dirname "$PID_FILE")/wifi-monitor-iface"
    
    # Verify it's running
    sleep 2
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        disable_monitor_mode "$MONITOR_IFACE"
        error "Failed to start tcpdump"
    fi
    
    log "✓ WiFi capture started (PID: $pid)"
}

stop_capture() {
    check_root
    
    if [[ ! -f "$PID_FILE" ]]; then
        log "WiFi capture is not running"
        return 0
    fi
    
    local pid=$(cat "$PID_FILE")
    local iface_file="$(dirname "$PID_FILE")/wifi-monitor-iface"
    local monitor_iface=$(cat "$iface_file" 2>/dev/null || echo "")
    
    log "Stopping WiFi capture (PID: $pid)..."
    
    # Stop tcpdump
    if kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null || true
        sleep 2
        kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
    fi
    
    rm -f "$PID_FILE"
    
    # Disable monitor mode
    if [[ -n "$monitor_iface" ]]; then
        # Get base interface name (remove 'mon' suffix if present)
        local base_iface="${monitor_iface%mon}"
        disable_monitor_mode "$monitor_iface"
        rm -f "$iface_file"
    fi
    
    log "✓ WiFi capture stopped"
}

status_capture() {
    load_config
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "WiFi Packet Capture Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Configuration
    echo ""
    echo "Configuration:"
    echo "  Enabled: ${WIFI_CAPTURE_ENABLED:-no}"
    echo "  Channel: ${WIFI_CAPTURE_CHANNEL:-11}"
    echo "  Max size: ${WIFI_CAPTURE_MAX_SIZE_MB:-100}MB"
    echo "  Max files: ${WIFI_CAPTURE_MAX_FILES:-50}"
    echo "  Filter: ${WIFI_CAPTURE_FILTER:-(none)}"
    
    # Interface
    echo ""
    echo "Interface:"
    local wifi_iface=$(detect_wifi_interface) || wifi_iface="(not detected)"
    echo "  Name: $wifi_iface"
    
    if [[ -f "$(dirname "$PID_FILE")/wifi-monitor-iface" ]]; then
        local monitor_iface=$(cat "$(dirname "$PID_FILE")/wifi-monitor-iface")
        echo "  Monitor: $monitor_iface"
        
        if command -v iw &>/dev/null && ip link show "$monitor_iface" &>/dev/null; then
            local channel=$(iw dev "$monitor_iface" info | grep channel | awk '{print $2}')
            echo "  Channel: ${channel:-(unknown)}"
        fi
    fi
    
    # Capture status
    echo ""
    echo "Capture:"
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  Status: RUNNING"
            echo "  PID: $pid"
            
            # Count packets
            if command -v netstat &>/dev/null; then
                echo "  Packets: (use tcpdump -r to count)"
            fi
        else
            echo "  Status: STOPPED (stale PID)"
        fi
    else
        echo "  Status: STOPPED"
    fi
    
    # Storage
    echo ""
    echo "Storage:"
    echo "  Directory: $CAPTURE_DIR"
    if [[ -d "$CAPTURE_DIR" ]]; then
        local file_count=$(find "$CAPTURE_DIR" -name "wifi-*.pcap" 2>/dev/null | wc -l)
        local total_size=$(du -sh "$CAPTURE_DIR" 2>/dev/null | awk '{print $1}')
        echo "  Files: $file_count"
        echo "  Total size: ${total_size:-0}"
    else
        echo "  Files: 0"
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

list_captures() {
    echo "WiFi Capture Files:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [[ ! -d "$CAPTURE_DIR" ]] || [[ -z "$(ls -A "$CAPTURE_DIR" 2>/dev/null)" ]]; then
        echo "(No captures found)"
        return 0
    fi
    
    find "$CAPTURE_DIR" -name "wifi-*.pcap" -type f -printf "%T@ %s %p\n" | \
        sort -rn | \
        while read -r timestamp size path; do
            local date=$(date -d "@${timestamp}" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || date -r "${timestamp}" "+%Y-%m-%d %H:%M:%S")
            local size_mb=$(echo "scale=2; $size / 1048576" | bc 2>/dev/null || echo "0")
            local filename=$(basename "$path")
            printf "%s  %8.2f MB  %s\n" "$date" "$size_mb" "$filename"
        done
}

usage() {
    cat << EOF
Usage: $0 {start|stop|restart|status|list}

Commands:
  start    Start WiFi packet capture (monitor mode)
  stop     Stop WiFi packet capture
  restart  Restart WiFi capture
  status   Show current status
  list     List captured files

Config file: $CONFIG_FILE
Capture directory: $CAPTURE_DIR
EOF
    exit 1
}

main() {
    case "${1:-}" in
        start)
            start_capture
            ;;
        stop)
            stop_capture
            ;;
        restart)
            stop_capture
            sleep 2
            start_capture
            ;;
        status)
            status_capture
            ;;
        list)
            list_captures
            ;;
        *)
            usage
            ;;
    esac
}

main "$@"
