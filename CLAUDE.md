# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NetworkTap is a network tap/monitoring appliance for the OnLogic FR201 (2-NIC Linux). It combines passive packet capture (tcpdump), IDS (Suricata + Zeek), and a FastAPI web dashboard. Target OS is Debian 12+/Ubuntu 22.04+.

**Version:** 0.0.1-beta

## Common Commands

```bash
# Install on target appliance (requires root, Debian/Ubuntu)
sudo bash install.sh

# Health check (validates services, interfaces, disk, memory)
sudo /opt/networktap/scripts/health_check.sh

# Check all services
systemctl status networktap-*

# Run the web app locally for development
cd web
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8443 --reload

# Switch operating mode
sudo /opt/networktap/scripts/switch_mode.sh bridge
sudo /opt/networktap/scripts/switch_mode.sh span

# Manual storage cleanup
sudo /opt/networktap/scripts/storage_cleanup.sh
```

There is no test suite, linter, or build step. The frontend is vanilla JS with no bundler. Validation is done via `health_check.sh` and manual API testing.

## Architecture

### Two Operating Modes
- **SPAN mode** (default): NIC1 passively monitors a switch SPAN port (promiscuous, no IP). NIC2 is the management interface (SSH, web UI).
- **Bridge mode**: NIC1 + NIC2 form a transparent L2 bridge. Management access is via the bridge IP.

### Data Flow
```
Network Traffic
  → NIC1 (or bridge)
    → tcpdump (writes rotating pcaps to /var/lib/networktap/captures/)
    → Suricata (writes EVE JSON alerts to /var/log/suricata/eve.json)
    → Zeek (writes JSON logs to /var/log/zeek/)

FastAPI backend (web/app.py)
  → AlertWatcher: tails eve.json, broadcasts new alerts to WebSocket clients
  → REST API: reads psutil stats, systemctl states, pcap file listings, parsed logs
  → Serves SPA frontend at /

Browser SPA
  → REST calls with HTTP Basic Auth for all data
  → WebSocket /ws/alerts for real-time Suricata alert streaming
```

### Configuration
Single config file: `networktap.conf` (symlinked to `/etc/networktap.conf`). Shell-style `KEY=VALUE` format. Sourced directly by bash scripts, parsed by `web/core/config.py` into a `NetworkTapConfig` dataclass with `@lru_cache`. When mode changes at runtime, `config.get_config.cache_clear()` is called.

Computed properties `capture_interface` and `management_interface` auto-resolve based on mode and `auto` settings.

### Backend (web/)
- **Entry point**: `web/app.py` — FastAPI app with lifespan manager that starts the AlertWatcher background task
- **`core/config.py`**: Loads config from `/etc/networktap.conf` (or project-local fallback)
- **`core/auth.py`**: HTTP Basic auth via FastAPI `Depends()`, timing-safe comparison
- **`core/alert_parser.py`**: `AlertWatcher` class polls eve.json for new lines every 1s, parses alert entries, invokes async broadcast callback. Also has `parse_suricata_alerts()` and `parse_zeek_alerts()` for on-demand reads with efficient tail-reading
- **`core/capture_manager.py`**: Controls tcpdump via `systemctl start/stop networktap-capture`. Lists pcap files with path traversal prevention
- **`core/system_monitor.py`**: psutil-based stats (CPU, memory, disk, interfaces). Checks service states via subprocess `systemctl is-active`
- **`core/network_manager.py`**: Mode info, mode switching (calls `switch_mode.sh`), interface detail via `ip -j`
- **API routers** (`api/routes_*.py`): 5 routers mounted at `/api/system`, `/api/capture`, `/api/alerts`, `/api/config`, `/api/pcaps`. All require auth via `Depends(verify_credentials)`

### Frontend (web/static/, web/templates/)
Vanilla JS SPA with no build tool. Each page is an IIFE module exporting a `render(container)` function.

- **`app.js`**: Hash-based router (`#dashboard`, `#captures`, etc.), global `api()` helper that adds Basic Auth header, `toast()` notifications, utility formatters (`formatBytes`, `formatUptime`, etc.), global status polling every 10s
- **`websocket.js`**: `WS` module — connects to `/ws/alerts`, auto-reconnects with exponential backoff, ping/pong keep-alive, exposes `onAlert` callback
- **`dashboard.js`**: 4 stat cards, service list, interface list, traffic sparkline (30-point history), recent alerts feed. Refreshes every 5s
- **`alerts.js`**: Real-time alerts table. Receives live alerts via `WS.onAlert`, supports source filtering and text search
- **`settings.js`**: Stores credentials in localStorage (`Settings.getCredentials()` is used by `api()` for auth headers). Displays read-only server config

CSS uses a dark theme with CSS variables (accent: `#00d4aa`). Responsive down to tablet.

### Systemd Services (services/)
5 services + 1 timer. All read `/etc/networktap.conf` via `EnvironmentFile`. The web service runs uvicorn; capture service runs `start_capture.sh`; Suricata and Zeek run their respective daemons; cleanup timer fires hourly to enforce pcap retention.

### Shell Scripts
- **`setup/`**: 7 install-time scripts run sequentially by `install.sh`. Handle package installation, network config (systemd-networkd), IDS setup, firewall (UFW), and service deployment
- **`scripts/`**: 5 runtime scripts. `start_capture.sh` builds tcpdump args from config and `exec`s tcpdump. `switch_mode.sh` updates config, reconfigures network, restarts services. `storage_cleanup.sh` enforces retention and does emergency cleanup on low disk

### Key Integration Points
- Scripts and Python both consume `networktap.conf` — scripts via `source`, Python via custom parser
- Backend controls services via `subprocess.run(["systemctl", ...])`
- AlertWatcher watches the Suricata EVE log file position and broadcasts to WebSocket clients
- Mode switching from the web UI calls `network_manager.switch_mode()` → `switch_mode.sh` → reconfigures network + restarts services → clears config cache
