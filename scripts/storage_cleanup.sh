#!/usr/bin/env bash
# Clean up old pcap files and manage storage
set -euo pipefail

source /etc/networktap.conf

PCAP_DIR="${CAPTURE_DIR}"

echo "[+] Storage cleanup started at $(date)"

# Delete pcaps older than retention period
if [[ -d "$PCAP_DIR" ]]; then
    old_count=$(find "$PCAP_DIR" -name "*.pcap" -o -name "*.pcap.gz" -mtime +"$RETENTION_DAYS" 2>/dev/null | wc -l)
    if [[ "$old_count" -gt 0 ]]; then
        echo "[+] Removing ${old_count} pcap files older than ${RETENTION_DAYS} days..."
        find "$PCAP_DIR" \( -name "*.pcap" -o -name "*.pcap.gz" \) -mtime +"$RETENTION_DAYS" -delete
    else
        echo "[i] No pcap files older than ${RETENTION_DAYS} days"
    fi
fi

# Check disk usage
DISK_USAGE=$(df "$PCAP_DIR" | awk 'NR==2 {print $5}' | tr -d '%')
DISK_FREE=$((100 - DISK_USAGE))

echo "[i] Disk usage: ${DISK_USAGE}% (${DISK_FREE}% free)"

# Emergency cleanup if disk is critically low
if [[ "$DISK_FREE" -lt "$MIN_FREE_DISK_PCT" ]]; then
    echo "[!] CRITICAL: Disk space below ${MIN_FREE_DISK_PCT}%!"
    echo "[!] Emergency cleanup: removing oldest pcap files..."

    # Remove oldest files until we're above threshold or no files left
    while [[ "$DISK_FREE" -lt "$MIN_FREE_DISK_PCT" ]]; do
        oldest=$(find "$PCAP_DIR" \( -name "*.pcap" -o -name "*.pcap.gz" \) -printf '%T+ %p\n' 2>/dev/null | sort | head -1 | cut -d' ' -f2-)
        if [[ -z "$oldest" ]]; then
            echo "[!] No more pcap files to remove!"
            break
        fi
        echo "[!] Removing: ${oldest}"
        rm -f "$oldest"
        DISK_USAGE=$(df "$PCAP_DIR" | awk 'NR==2 {print $5}' | tr -d '%')
        DISK_FREE=$((100 - DISK_USAGE))
    done

    echo "[i] Disk now at ${DISK_USAGE}% usage"
fi

# Rotate Suricata eve.json if it's getting large (>500MB)
if [[ -f "$SURICATA_EVE_LOG" ]]; then
    EVE_SIZE=$(stat -f%z "$SURICATA_EVE_LOG" 2>/dev/null || stat -c%s "$SURICATA_EVE_LOG" 2>/dev/null || echo 0)
    if [[ "$EVE_SIZE" -gt 524288000 ]]; then
        echo "[+] Rotating large eve.json ($(numfmt --to=iec "$EVE_SIZE"))"
        mv "$SURICATA_EVE_LOG" "${SURICATA_EVE_LOG}.$(date +%Y%m%d%H%M%S)"
        gzip "${SURICATA_EVE_LOG}."* 2>/dev/null || true
        # Signal Suricata to reopen log
        systemctl reload networktap-suricata.service 2>/dev/null || true
    fi
fi

echo "[+] Storage cleanup complete"
