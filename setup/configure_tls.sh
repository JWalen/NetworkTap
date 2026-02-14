#!/usr/bin/env bash
# NetworkTap - TLS/HTTPS Configuration
# Generates self-signed certificates or configures Let's Encrypt
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /etc/networktap.conf 2>/dev/null || source "${SCRIPT_DIR}/../networktap.conf"

CERT_DIR="${TLS_CERT_DIR:-/etc/networktap/tls}"
CERT_FILE="${CERT_DIR}/server.crt"
KEY_FILE="${CERT_DIR}/server.key"
DAYS_VALID=365
HOSTNAME="${TLS_HOSTNAME:-$(hostname -f 2>/dev/null || hostname)}"

log()  { echo "[+] $*"; }
warn() { echo "[!] $*"; }
err()  { echo "[✗] $*" >&2; }

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  generate              Generate self-signed certificate"
    echo "  letsencrypt <domain>  Obtain Let's Encrypt certificate"
    echo "  status                Show current certificate status"
    echo "  renew                 Renew Let's Encrypt certificate"
    echo ""
    echo "Options:"
    echo "  --hostname <name>     Override hostname for certificate"
    echo ""
    exit 1
}

ensure_root() {
    if [[ $EUID -ne 0 ]]; then
        err "This script must be run as root"
        exit 1
    fi
}

generate_self_signed() {
    ensure_root
    log "Generating self-signed certificate for ${HOSTNAME}..."

    mkdir -p "$CERT_DIR"
    chmod 700 "$CERT_DIR"

    # Generate private key and certificate
    openssl req -x509 -nodes -days "$DAYS_VALID" \
        -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/CN=${HOSTNAME}/O=NetworkTap/OU=Appliance" \
        -addext "subjectAltName=DNS:${HOSTNAME},DNS:localhost,IP:127.0.0.1" \
        2>/dev/null

    chmod 600 "$KEY_FILE"
    chmod 644 "$CERT_FILE"

    log "Certificate generated:"
    log "  Certificate: ${CERT_FILE}"
    log "  Private Key: ${KEY_FILE}"
    log "  Valid for: ${DAYS_VALID} days"

    # Update config to enable TLS
    update_config_tls "yes" "$CERT_FILE" "$KEY_FILE"

    log "TLS enabled. Restart networktap-web to apply."
}

setup_letsencrypt() {
    local domain="$1"
    ensure_root

    log "Setting up Let's Encrypt for ${domain}..."

    # Install certbot if not present
    if ! command -v certbot &>/dev/null; then
        log "Installing certbot..."
        apt-get update -qq
        apt-get install -y -qq certbot
    fi

    # Stop web service temporarily for standalone mode
    systemctl stop networktap-web 2>/dev/null || true

    # Obtain certificate
    certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email "admin@${domain}" \
        --domain "$domain" \
        --cert-path "$CERT_FILE" \
        --key-path "$KEY_FILE"

    # Create symlinks to Let's Encrypt certs
    local le_dir="/etc/letsencrypt/live/${domain}"
    ln -sf "${le_dir}/fullchain.pem" "$CERT_FILE"
    ln -sf "${le_dir}/privkey.pem" "$KEY_FILE"

    update_config_tls "yes" "$CERT_FILE" "$KEY_FILE"

    # Setup auto-renewal
    setup_renewal_timer

    # Restart web service
    systemctl start networktap-web

    log "Let's Encrypt certificate installed for ${domain}"
}

setup_renewal_timer() {
    cat > /etc/systemd/system/networktap-certbot.service <<EOF
[Unit]
Description=NetworkTap Let's Encrypt Renewal
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --post-hook "systemctl reload networktap-web"
EOF

    cat > /etc/systemd/system/networktap-certbot.timer <<EOF
[Unit]
Description=NetworkTap Certificate Renewal Timer

[Timer]
OnCalendar=*-*-* 02:30:00
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
EOF

    systemctl daemon-reload
    systemctl enable --now networktap-certbot.timer
    log "Auto-renewal timer configured"
}

update_config_tls() {
    local enabled="$1"
    local cert="$2"
    local key="$3"
    local conf="/etc/networktap.conf"

    # Add or update TLS settings
    if grep -q "^TLS_ENABLED=" "$conf" 2>/dev/null; then
        sed -i "s|^TLS_ENABLED=.*|TLS_ENABLED=${enabled}|" "$conf"
    else
        echo "" >> "$conf"
        echo "# ── TLS/HTTPS ─────────────────────────────────────────────────" >> "$conf"
        echo "TLS_ENABLED=${enabled}" >> "$conf"
    fi

    if grep -q "^TLS_CERT=" "$conf" 2>/dev/null; then
        sed -i "s|^TLS_CERT=.*|TLS_CERT=${cert}|" "$conf"
    else
        echo "TLS_CERT=${cert}" >> "$conf"
    fi

    if grep -q "^TLS_KEY=" "$conf" 2>/dev/null; then
        sed -i "s|^TLS_KEY=.*|TLS_KEY=${key}|" "$conf"
    else
        echo "TLS_KEY=${key}" >> "$conf"
    fi
}

show_status() {
    echo "TLS Certificate Status"
    echo "======================"

    if [[ -f "$CERT_FILE" ]]; then
        echo "Certificate: ${CERT_FILE}"
        echo ""
        openssl x509 -in "$CERT_FILE" -noout -subject -dates -issuer 2>/dev/null || echo "  (unable to parse)"
        echo ""

        # Check expiry
        local expiry
        expiry=$(openssl x509 -in "$CERT_FILE" -noout -enddate 2>/dev/null | cut -d= -f2)
        local expiry_epoch
        expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || echo 0)
        local now_epoch
        now_epoch=$(date +%s)
        local days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

        if [[ $days_left -lt 0 ]]; then
            warn "Certificate EXPIRED!"
        elif [[ $days_left -lt 30 ]]; then
            warn "Certificate expires in ${days_left} days"
        else
            log "Certificate valid for ${days_left} more days"
        fi
    else
        warn "No certificate found at ${CERT_FILE}"
        echo "Run '$0 generate' to create a self-signed certificate"
    fi

    echo ""
    echo "Config: TLS_ENABLED=${TLS_ENABLED:-no}"
}

renew_certs() {
    ensure_root
    log "Renewing certificates..."
    certbot renew --quiet
    systemctl reload networktap-web 2>/dev/null || true
    log "Renewal complete"
}

# ── Main ─────────────────────────────────────────────────────────
[[ $# -ge 1 ]] || usage

# Parse options
while [[ $# -gt 0 ]]; do
    case "$1" in
        --hostname)
            HOSTNAME="$2"
            shift 2
            ;;
        generate)
            generate_self_signed
            exit 0
            ;;
        letsencrypt)
            [[ $# -ge 2 ]] || { err "Domain required"; usage; }
            setup_letsencrypt "$2"
            exit 0
            ;;
        status)
            show_status
            exit 0
            ;;
        renew)
            renew_certs
            exit 0
            ;;
        *)
            usage
            ;;
    esac
done
