#!/usr/bin/env bash
# NetworkTap Update Script
# Performs in-place upgrade with backup and rollback capability

set -euo pipefail

SOURCE_DIR="${1:-}"
INSTALL_DIR="${2:-/opt/networktap}"
BACKUP_DIR="/opt/networktap-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

usage() {
    echo "Usage: $0 <source_dir> [install_dir]"
    echo ""
    echo "  source_dir   Directory containing new version"
    echo "  install_dir  Installation directory (default: /opt/networktap)"
    exit 1
}

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    log "ERROR: $*" >&2
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        # Allow non-root if called via sudo (SUDO_USER set) or FORCE mode
        if [[ -n "${SUDO_USER:-}" ]] || [[ "${FORCE:-}" == "yes" ]]; then
            log "Warning: Running as non-root (EUID=$EUID)"
        else
            error "This script must be run as root"
        fi
    fi
}

validate_source() {
    if [[ ! -d "$SOURCE_DIR" ]]; then
        error "Source directory not found: $SOURCE_DIR"
    fi
    
    # Check for essential components
    local required_dirs=("web" "scripts" "services")
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$SOURCE_DIR/$dir" ]]; then
            error "Missing required directory in source: $dir"
        fi
    done
    
    # Check for VERSION file
    if [[ ! -f "$SOURCE_DIR/VERSION" ]]; then
        error "VERSION file not found in source"
    fi
}

stop_services() {
    log "Stopping NetworkTap services..."

    local services=(
        "networktap-capture"
        "networktap-suricata"
        "networktap-zeek"
        "networktap-stats"
        "networktap-display"
    )

    # Only stop web service if not called from the web UI
    if [[ "${SKIP_WEB_RESTART:-}" != "yes" ]]; then
        services=("networktap-web" "${services[@]}")
    else
        log "  Skipping networktap-web (called from web UI)"
    fi

    for svc in "${services[@]}"; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            log "  Stopping $svc..."
            systemctl stop "$svc" || true
        fi
    done
}

start_services() {
    log "Starting NetworkTap services..."

    local services=(
        "networktap-capture"
        "networktap-suricata"
        "networktap-zeek"
        "networktap-stats"
        "networktap-display"
    )

    # Only start web service if not called from the web UI
    if [[ "${SKIP_WEB_RESTART:-}" != "yes" ]]; then
        services=("networktap-web" "${services[@]}")
    else
        log "  Skipping networktap-web restart (called from web UI, will restart separately)"
    fi

    for svc in "${services[@]}"; do
        if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
            log "  Starting $svc..."
            systemctl start "$svc" || log "  Warning: Failed to start $svc"
        fi
    done
}

backup_config() {
    log "Backing up configuration..."
    
    local config_backup="$BACKUP_DIR/config-$TIMESTAMP"
    mkdir -p "$config_backup"
    
    # Backup config file
    if [[ -f /etc/networktap.conf ]]; then
        cp /etc/networktap.conf "$config_backup/"
    fi
    
    # Backup database if exists
    if [[ -f /var/lib/networktap/stats.db ]]; then
        cp /var/lib/networktap/stats.db "$config_backup/"
    fi
    
    # Backup custom rules
    if [[ -d /etc/suricata/rules/custom ]]; then
        cp -r /etc/suricata/rules/custom "$config_backup/"
    fi
    
    log "Configuration backed up to $config_backup"
}

update_files() {
    log "Updating files..."
    
    # Update web application
    log "  Updating web application..."
    rsync -a --delete "$SOURCE_DIR/web/" "$INSTALL_DIR/web/"
    
    # Update scripts
    log "  Updating scripts..."
    rsync -a "$SOURCE_DIR/scripts/" "$INSTALL_DIR/scripts/"
    chmod +x "$INSTALL_DIR/scripts/"*.sh
    
    # Update setup scripts
    if [[ -d "$SOURCE_DIR/setup" ]]; then
        log "  Updating setup scripts..."
        rsync -a "$SOURCE_DIR/setup/" "$INSTALL_DIR/setup/"
        chmod +x "$INSTALL_DIR/setup/"*.sh
    fi
    
    # Update systemd services (but don't overwrite active configs)
    log "  Updating systemd services..."
    for svc in "$SOURCE_DIR/services/"*.service; do
        if [[ -f "$svc" ]]; then
            local svc_name=$(basename "$svc")
            cp "$svc" /etc/systemd/system/
        fi
    done
    
    # Update documentation
    log "  Updating documentation..."
    for doc in README.md CHANGELOG.md; do
        if [[ -f "$SOURCE_DIR/$doc" ]]; then
            cp "$SOURCE_DIR/$doc" "$INSTALL_DIR/"
        fi
    done
    
    # Update VERSION file
    cp "$SOURCE_DIR/VERSION" "$INSTALL_DIR/VERSION"
}

update_database() {
    log "Checking for database migrations..."
    
    # Check if migration script exists
    if [[ -f "$SOURCE_DIR/scripts/migrate_db.sh" ]]; then
        log "  Running database migrations..."
        bash "$SOURCE_DIR/scripts/migrate_db.sh" || log "  Warning: Migration had issues"
    fi
}

update_dependencies() {
    log "Updating Python dependencies..."

    if [[ -f "$SOURCE_DIR/web/requirements.txt" ]]; then
        # Update in virtual environment if it exists
        # Venv lives at $INSTALL_DIR/venv (not inside web/)
        if [[ -d "$INSTALL_DIR/venv" ]]; then
            source "$INSTALL_DIR/venv/bin/activate"
            pip install --quiet -r "$SOURCE_DIR/web/requirements.txt"
            deactivate
        elif [[ -d "$INSTALL_DIR/web/venv" ]]; then
            source "$INSTALL_DIR/web/venv/bin/activate"
            pip install --quiet -r "$SOURCE_DIR/web/requirements.txt"
            deactivate
        else
            pip3 install --quiet -r "$SOURCE_DIR/web/requirements.txt"
        fi
    fi
}

reload_systemd() {
    log "Reloading systemd configuration..."
    systemctl daemon-reload
}

verify_installation() {
    log "Verifying installation..."

    # Check essential files exist
    local essential_files=(
        "$INSTALL_DIR/VERSION"
        "$INSTALL_DIR/web/app.py"
        "$INSTALL_DIR/scripts/health_check.sh"
    )

    for file in "${essential_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            error "Verification failed: Missing $file"
        fi
    done

    # Check web app imports using the venv python if available
    local py="python3"
    if [[ -x "$INSTALL_DIR/venv/bin/python3" ]]; then
        py="$INSTALL_DIR/venv/bin/python3"
    elif [[ -x "$INSTALL_DIR/web/venv/bin/python3" ]]; then
        py="$INSTALL_DIR/web/venv/bin/python3"
    fi

    cd "$INSTALL_DIR/web"
    if ! "$py" -c "import app" 2>/dev/null; then
        log "Warning: Web app import check failed (may need service restart)"
    fi

    log "Verification passed"
}

run_new_setup_scripts() {
    log "Running setup scripts for new/updated features..."

    # FR202 front panel display — always re-run to pick up new dependencies
    if [[ -f "$INSTALL_DIR/setup/configure_display.sh" ]]; then
        log "  Configuring FR202 front panel display..."
        bash "$INSTALL_DIR/setup/configure_display.sh" || log "  Warning: Display setup had issues"
    fi

    # AI features
    if [[ -f "$INSTALL_DIR/setup/configure_ai.sh" ]]; then
        if ! systemctl is-enabled --quiet networktap-anomaly 2>/dev/null; then
            log "  Configuring AI features..."
            bash "$INSTALL_DIR/setup/configure_ai.sh" || log "  Warning: AI setup had issues"
        fi
    fi
}

restart_console() {
    # Restart console/splash services so they pick up updated scripts
    log "Restarting console services..."
    systemctl restart networktap-console.service 2>/dev/null || true
    systemctl restart networktap-splash.service 2>/dev/null || true
}

main() {
    [[ $# -ge 1 ]] || usage
    
    check_root
    validate_source
    
    local new_version=$(cat "$SOURCE_DIR/VERSION")
    local old_version=$(cat "$INSTALL_DIR/VERSION" 2>/dev/null || echo "unknown")
    
    log "=================================="
    log "NetworkTap Update"
    log "=================================="
    log "Current version: $old_version"
    log "New version:     $new_version"
    log "Install dir:     $INSTALL_DIR"
    log "=================================="
    
    # Confirm if running interactively
    if [[ -t 0 ]] && [[ "${FORCE:-}" != "yes" ]]; then
        read -p "Continue with update? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "Update cancelled"
            exit 0
        fi
    fi
    
    # Perform update
    backup_config
    stop_services
    update_files
    update_dependencies
    update_database
    reload_systemd
    run_new_setup_scripts
    verify_installation
    start_services
    restart_console
    
    log "=================================="
    log "Update completed successfully!"
    log "Updated from $old_version to $new_version"
    log "=================================="
    
    # Run health check
    if [[ -f "$INSTALL_DIR/scripts/health_check.sh" ]]; then
        log ""
        log "Running health check..."
        bash "$INSTALL_DIR/scripts/health_check.sh" || true
    fi
}

main "$@"
