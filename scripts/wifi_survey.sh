#!/usr/bin/env bash
# WiFi Site Survey Tool
# Performs wireless site surveys: signal analysis, channel utilization, AP detection

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="/etc/networktap.conf"
SURVEY_DIR="/var/lib/networktap/wifi-survey"
SURVEY_FILE="${SURVEY_DIR}/survey.json"

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

check_tools() {
    local missing=()
    
    for tool in iw iwlist; do
        if ! command -v "$tool" &>/dev/null; then
            missing+=("$tool")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing required tools: ${missing[*]}. Install with: apt install wireless-tools iw"
    fi
}

scan_networks() {
    local iface="$1"
    local timeout="${2:-10}"
    
    log "Scanning WiFi networks on $iface..."
    
    # Ensure interface is up
    ip link set "$iface" up 2>/dev/null || true
    
    # Try iw first (newer)
    if command -v iw &>/dev/null; then
        timeout "$timeout" iw dev "$iface" scan 2>/dev/null || {
            log "  iw scan failed, trying iwlist..."
            timeout "$timeout" iwlist "$iface" scan 2>/dev/null || {
                error "Failed to scan networks"
            }
        }
    else
        # Fall back to iwlist
        timeout "$timeout" iwlist "$iface" scan 2>/dev/null || error "Failed to scan networks"
    fi
}

parse_iw_scan() {
    local scan_output="$1"
    
    # Parse iw scan output into JSON
    # Format: BSS MAC (on wlan0), SSID, freq, signal, security, etc.
    
    local current_bss=""
    local current_ssid=""
    local current_freq=""
    local current_signal=""
    local current_security="Open"
    local ap_count=0
    
    echo "["
    
    while IFS= read -r line; do
        if [[ "$line" =~ ^BSS\ ([0-9a-f:]+) ]]; then
            # New AP entry - output previous if exists
            if [[ -n "$current_bss" ]]; then
                [[ $ap_count -gt 0 ]] && echo ","
                cat << EOF
  {
    "bssid": "$current_bss",
    "ssid": "$current_ssid",
    "frequency": ${current_freq:-0},
    "channel": $(freq_to_channel "$current_freq"),
    "signal": ${current_signal:-0},
    "security": "$current_security",
    "timestamp": "$(date -Iseconds)"
  }
EOF
                ((ap_count++))
            fi
            
            current_bss="${BASH_REMATCH[1]}"
            current_ssid=""
            current_freq=""
            current_signal=""
            current_security="Open"
            
        elif [[ "$line" =~ SSID:\ (.+) ]]; then
            current_ssid="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ freq:\ ([0-9]+) ]]; then
            current_freq="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ signal:\ (-?[0-9.]+) ]]; then
            current_signal="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ RSN: ]] || [[ "$line" =~ WPA: ]]; then
            current_security="WPA/WPA2"
        elif [[ "$line" =~ WEP: ]]; then
            current_security="WEP"
        fi
    done <<< "$scan_output"
    
    # Output last AP
    if [[ -n "$current_bss" ]]; then
        [[ $ap_count -gt 0 ]] && echo ","
        cat << EOF
  {
    "bssid": "$current_bss",
    "ssid": "$current_ssid",
    "frequency": ${current_freq:-0},
    "channel": $(freq_to_channel "$current_freq"),
    "signal": ${current_signal:-0},
    "security": "$current_security",
    "timestamp": "$(date -Iseconds)"
  }
EOF
    fi
    
    echo "]"
}

parse_iwlist_scan() {
    local scan_output="$1"
    
    # Parse iwlist scan output
    local current_bss=""
    local current_ssid=""
    local current_freq=""
    local current_channel=""
    local current_signal=""
    local current_quality=""
    local current_security="Open"
    local ap_count=0
    
    echo "["
    
    while IFS= read -r line; do
        line=$(echo "$line" | xargs)  # Trim whitespace
        
        if [[ "$line" =~ Address:\ ([0-9A-F:]+) ]]; then
            # New AP entry
            if [[ -n "$current_bss" ]]; then
                [[ $ap_count -gt 0 ]] && echo ","
                cat << EOF
  {
    "bssid": "$current_bss",
    "ssid": "$current_ssid",
    "frequency": ${current_freq:-0},
    "channel": ${current_channel:-0},
    "signal": ${current_signal:-0},
    "quality": ${current_quality:-0},
    "security": "$current_security",
    "timestamp": "$(date -Iseconds)"
  }
EOF
                ((ap_count++))
            fi
            
            current_bss="${BASH_REMATCH[1]}"
            current_ssid=""
            current_freq=""
            current_channel=""
            current_signal=""
            current_quality=""
            current_security="Open"
            
        elif [[ "$line" =~ ESSID:\"(.*)\" ]]; then
            current_ssid="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ Frequency:([0-9.]+) ]]; then
            current_freq="${BASH_REMATCH[1]}"
            current_freq=$(echo "$current_freq * 1000" | bc 2>/dev/null || echo "0")
            current_freq=${current_freq%.*}
        elif [[ "$line" =~ Channel:([0-9]+) ]] || [[ "$line" =~ Channel\ ([0-9]+) ]]; then
            current_channel="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ Signal\ level=(-?[0-9]+) ]]; then
            current_signal="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ Quality=([0-9]+) ]]; then
            current_quality="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ WPA ]] || [[ "$line" =~ WPA2 ]]; then
            current_security="WPA/WPA2"
        elif [[ "$line" =~ WEP ]]; then
            current_security="WEP"
        fi
    done <<< "$scan_output"
    
    # Output last AP
    if [[ -n "$current_bss" ]]; then
        [[ $ap_count -gt 0 ]] && echo ","
        cat << EOF
  {
    "bssid": "$current_bss",
    "ssid": "$current_ssid",
    "frequency": ${current_freq:-0},
    "channel": ${current_channel:-0},
    "signal": ${current_signal:-0},
    "quality": ${current_quality:-0},
    "security": "$current_security",
    "timestamp": "$(date -Iseconds)"
  }
EOF
    fi
    
    echo "]"
}

freq_to_channel() {
    local freq="$1"
    
    if [[ -z "$freq" ]] || [[ "$freq" == "0" ]]; then
        echo "0"
        return
    fi
    
    # 2.4 GHz band
    if (( freq >= 2412 && freq <= 2484 )); then
        if (( freq == 2484 )); then
            echo "14"
        else
            echo $(( (freq - 2407) / 5 ))
        fi
    # 5 GHz band
    elif (( freq >= 5170 && freq <= 5825 )); then
        echo $(( (freq - 5000) / 5 ))
    else
        echo "0"
    fi
}

analyze_channels() {
    local survey_json="$1"
    
    log "Analyzing channel utilization..."
    
    # Count APs per channel
    if command -v jq &>/dev/null; then
        jq -r '.[] | "\(.channel)"' <<< "$survey_json" | sort | uniq -c | sort -rn
    else
        # Fallback without jq
        grep '"channel":' <<< "$survey_json" | grep -o '[0-9]*' | sort | uniq -c | sort -rn
    fi
}

run_survey() {
    check_root
    load_config
    check_tools
    
    # Detect interface
    WIFI_IFACE=$(detect_wifi_interface) || error "No WiFi interface found"
    log "WiFi interface: $WIFI_IFACE"
    
    # Create survey directory
    mkdir -p "$SURVEY_DIR"
    
    # Run scan
    local scan_output=$(scan_networks "$WIFI_IFACE" 15)
    
    # Parse results
    local survey_json=""
    if echo "$scan_output" | grep -q "^BSS"; then
        # iw format
        survey_json=$(parse_iw_scan "$scan_output")
    else
        # iwlist format
        survey_json=$(parse_iwlist_scan "$scan_output")
    fi
    
    # Save to file
    echo "$survey_json" > "$SURVEY_FILE"
    
    # Count APs
    local ap_count=$(echo "$survey_json" | grep -c '"bssid"' || echo "0")
    
    log "✓ Survey complete: $ap_count access points detected"
    
    # Show channel utilization
    if [[ $ap_count -gt 0 ]]; then
        echo ""
        echo "Channel Utilization:"
        analyze_channels "$survey_json"
    fi
    
    echo ""
    log "Results saved to: $SURVEY_FILE"
}

show_results() {
    if [[ ! -f "$SURVEY_FILE" ]]; then
        echo "No survey results found. Run 'survey' first."
        return 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "WiFi Site Survey Results"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local survey_json=$(cat "$SURVEY_FILE")
    local ap_count=$(echo "$survey_json" | grep -c '"bssid"' || echo "0")
    
    echo ""
    echo "Total Access Points: $ap_count"
    echo ""
    
    if [[ $ap_count -eq 0 ]]; then
        echo "(No access points found)"
        return 0
    fi
    
    # Display table
    printf "%-20s %-32s %-10s %-10s %-12s\n" "BSSID" "SSID" "Channel" "Signal" "Security"
    echo "────────────────────────────────────────────────────────────────────────────────"
    
    if command -v jq &>/dev/null; then
        jq -r '.[] | "\(.bssid) \(.ssid) \(.channel) \(.signal) \(.security)"' "$SURVEY_FILE" | \
            while read -r bssid ssid channel signal security; do
                printf "%-20s %-32s %-10s %-10s %-12s\n" \
                    "$bssid" "${ssid:0:32}" "$channel" "${signal} dBm" "$security"
            done
    else
        # Fallback without jq (basic parsing)
        grep -A 6 '"bssid"' "$SURVEY_FILE" | grep -v '^--$' | \
            awk -F'"' '/"bssid"/{bssid=$4} /"ssid"/{ssid=$4} /"channel"/{channel=$4} /"signal"/{signal=$4} /"security"/{security=$4; print bssid, ssid, channel, signal, security}'
    fi
    
    echo ""
    echo "Channel Utilization:"
    analyze_channels "$survey_json"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

usage() {
    cat << EOF
Usage: $0 {survey|show}

Commands:
  survey   Run a new WiFi site survey
  show     Display most recent survey results

Output: $SURVEY_FILE
EOF
    exit 1
}

main() {
    case "${1:-}" in
        survey)
            run_survey
            ;;
        show)
            show_results
            ;;
        *)
            usage
            ;;
    esac
}

main "$@"
