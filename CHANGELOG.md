# Changelog

All notable changes to NetworkTap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.37] - 2026-02-20

### Fixed
- **Site survey still timing out**: Endpoint had hardcoded `timeout=30` that overrode the default — increased to 90s
- **WiFi client scan timeout**: Increased from 30s to 60s

## [1.0.36] - 2026-02-20

### Fixed
- **Site survey timeout**: Increased scan timeout from 15s to 30s (bash) and API timeout from 30s to 60s — fixes "command timed out" errors
- **AP config form broken**: Added missing submit handler — "Update Configuration" button now works
- **WiFi connect double-stringify bug**: Fixed `JSON.stringify` being called twice on connect request body
- **WiFi connect timeout**: Increased DHCP wait from 15s to 30s for slow networks
- **hostapd client count**: Fixed incorrect `grep` pattern that was counting empty lines instead of MAC addresses
- **JSON SSID escaping**: SSIDs with quotes/special characters no longer break survey JSON output
- **Input validation**: SSID (1-32 chars), password (8-63 chars), and channel (1-14) validated on both frontend and backend
- **Monitor mode capture timeout**: Increased from 20s to 30s

### Added
- **WiFi AP config variables** in networktap.conf: WIFI_AP_SSID, WIFI_AP_PASSPHRASE, WIFI_AP_CHANNEL, WIFI_AP_IP, WIFI_AP_SUBNET

## [1.0.35] - 2026-02-20

### Fixed
- **Console login header**: Fixed `/etc/issue` splash (update_issue.sh) showing "Acquiring" — was looking at wrong interface after NIC swap
- **Split ASCII art** on all console screens (update_issue.sh, console_status.sh) — NETWORK on one line, TAP below
- **Default NIC fallback**: All console scripts now default to `eth0` for management instead of `eth1`

## [1.0.34] - 2026-02-20

### Fixed
- **Firewall reconfigured on NIC swap**: Changing NIC assignments now also re-runs `configure_firewall.sh` to update UFW rules for the new management interface

## [1.0.33] - 2026-02-20

### Changed
- **Clearer NIC labels**: Settings UI shows "Capture Interface" and "Management Interface" instead of NIC1/NIC2
- Simplified system info banner — removed redundant NIC1/NIC2 entries

## [1.0.32] - 2026-02-20

### Fixed
- **NIC swap now reconfigures networking**: Changing NIC1/NIC2 in Settings automatically re-runs `configure_network.sh` to update systemd-networkd files (promiscuous mode, IP assignment, offloading)
- Confirmation prompt warns that NIC changes will reconfigure networking

## [1.0.31] - 2026-02-20

### Changed
- **Interface dropdowns**: NIC1/NIC2, capture, Suricata, and Zeek interface fields now use dropdowns populated from available system interfaces instead of free text inputs
- **WiFi channel dropdown**: Channel selector uses dropdown (1-14) instead of free text

## [1.0.30] - 2026-02-20

### Added
- **NIC assignment editing**: NIC1/NIC2 can now be changed from Settings > Configuration > Interfaces
- **Updated help page**: Changelog and user guide now cover all versions through v1.0.29

## [1.0.29] - 2026-02-20

### Performance
- **Non-blocking CPU monitoring**: `psutil.cpu_percent` no longer blocks event loop for 500ms
- **Dashboard refresh 5s -> 10s**: Halves polling load on the CM4
- **Alert fetch limit 200 -> 20**: Dashboard only shows 8, was wasting bandwidth
- **Alerts API caching**: 5-second TTL cache avoids re-parsing log files every poll
- **Live alert filter debounced**: No longer runs on every single incoming WebSocket alert
- **Sparkline bar updates batched**: Uses `requestAnimationFrame` to avoid per-bar reflow

## [1.0.28] - 2026-02-20

### Performance
- **Capture status caching**: 5-second TTL cache on capture file listing avoids redundant directory scans
- **Zeek conn.log caching**: 30-second TTL cache on parsed connection data
- **Binary path caching**: `lru_cache` on capinfos/tshark/tcpdump path lookups
- **Port name caching**: `lru_cache(128)` on service name resolution
- **Efficient top-N**: Use `heapq.nlargest` instead of full sort for top talkers/ports
- **Debounced filters**: 300ms debounce on alert and terminal filter inputs
- **Timer cleanup**: Alerts and terminal pages properly clear all timers on page leave

## [1.0.27] - 2026-02-20

### Changed
- Swapped NIC assignments: eth1 is now capture, eth0 is now management/uplink

### Added
- **Reboot button** in Settings > Power with double confirmation prompt
- `POST /api/system/reboot` endpoint (admin only)

## [1.0.26] - 2026-02-20

### Changed
- **Larger, clearer logo**: "NETWORK" at 36px and "TAP" at 28px using clean bold font instead of block art
- **Logo moved up** to make room for the 64px clock which is now properly on-screen
- **Screensaver color picker**: Choose any color in Settings > Configuration > Display, with 9 preset swatches

## [1.0.25] - 2026-02-20

### Changed
- Screensaver clock doubled to 64px font — fills the space under the logo

## [1.0.24] - 2026-02-20

### Changed
- Screensaver clock enlarged from 11px to 32px font for better readability

## [1.0.23] - 2026-02-20

### Changed
- **Smaller logo**: "NETWORK" on first line, "TAP" on second, centered on the 320px display
- **Screensaver setting**: New toggle in Settings > Configuration > Display to enable/disable screensaver
- When screensaver is disabled, the display dims the backlight instead (previous behavior)

## [1.0.22] - 2026-02-20

### Added
- **Boot splash screen**: ASCII art "NETWORKTAP" logo displayed for 3 seconds on startup
- **Screensaver mode**: Pulsing logo with clock replaces simple backlight dimming on idle timeout
- Touch to wake from screensaver returns to the current page without changing

## [1.0.21] - 2026-02-20

### Fixed
- Fixed "failed to save" error when saving config from Settings page (double JSON.stringify bug)

## [1.0.20] - 2026-02-20

### Fixed
- **Power LED fix**: Auto-corrects `pwr_led_trigger=backlight` to `default-on` in config.txt
- Added power LED config to `configure_display.sh` for FR202

## [1.0.19] - 2026-02-20

### Added
- **Display settings in web UI**: Control FR202 display from Settings > Configuration > Display
  - Enable/disable display, refresh interval, backlight timeout, default page
- Display daemon reads settings from config file and reloads every 60s
- Service restart API endpoint (`POST /api/system/service/{name}/restart`)

## [1.0.18] - 2026-02-20

### Fixed
- Update script now always re-runs display setup to install new dependencies
- Ensures `smbus2`, `gpiod`, `gpiodevice` are installed during updates (not just fresh installs)
- Updated README with FR202 display documentation and correct version
- Updated CHANGELOG with all versions from 1.0.2 through 1.0.18

## [1.0.17] - 2026-02-20

### Added
- **Multi-page touch display**: 5 pages on the FR202 front panel (Dashboard, Network, Services, Alerts, System)
- Touch navigation via ST1633i controller (0x70 on I2C bus 5, GPIO 26 interrupt)
- Page indicator dots in header showing current position
- Backlight auto-dims after 2 minutes idle, tap to wake
- Network page: all interfaces with IP, state, speed, MAC
- Services page: all 7 services with status, sub-state, uptime
- Alerts page: total events, severity breakdown (High/Med/Low), top 5 signatures
- System page: hostname, uptime, CPU temp, load, kernel, memory/disk/PCAP storage, version, NIC config

## [1.0.16] - 2026-02-20

### Fixed
- **FR202 display pin configuration** (from OnLogic demo-display reference):
  - DC pin: GPIO 25 -> GPIO 16
  - Added reset pin: GPIO 27 (open-drain)
  - SPI mode: 0 -> 3
  - Rotation: 0 -> 180 degrees
- Disabled generic `dtparam=spi=on` per OnLogic docs (FR202 uses SPI3/SPI4 overlays)
- Backlight control uses `smbus2` library (matching OnLogic's `fr202-i2c`) with i2cset fallback
- Added `smbus2`, `gpiod`, `gpiodevice` to display dependencies

## [1.0.15] - 2026-02-19

### Fixed
- Display service now uses venv Python (`/opt/networktap/venv/bin/python3`) instead of system Python
- Fixed Pillow import failure that prevented display from rendering

## [1.0.14] - 2026-02-19

### Fixed
- FR202 display: added SPI3, SPI4, I2C1 (pins 44/45), I2C5 overlays to config.txt
- Added i2c-dev kernel module autoload at boot
- Fixed console status script UTF-8 locale detection

## [1.0.13] - 2026-02-19

### Fixed
- Update script now runs setup scripts for new features (e.g., display)
- Update script restarts console/splash services after update

## [1.0.12] - 2026-02-19

### Fixed
- Added `flush_cache` parameter to update check API endpoint
- Reduced GitHub API cache TTL from 15 minutes to 5 minutes
- Manual update checks now bypass cache

## [1.0.11] - 2026-02-19

### Added
- App version displayed in console splash screen and boot splash
- Version read from `/opt/networktap/VERSION`

## [1.0.10] - 2026-02-19

### Fixed
- Update script: corrected venv path from `$INSTALL_DIR/web/venv` to `$INSTALL_DIR/venv`
- Update verification: uses venv Python for import checks, downgraded to warning on failure

## [1.0.9] - 2026-02-19

### Added
- **FR202 front panel display**: Initial support for the OnLogic FR202 3.5" ST7789V TFT
- Display service (`networktap-display.service`) renders system status every 5 seconds
- Display setup script (`configure_display.sh`) configures SPI, I2C, and dependencies

## [1.0.7] - 2026-02-18

### Changed
- Consolidated Captures & PCAPs pages into unified UI
- Redesigned captures page layout

## [1.0.6] - 2026-02-18

### Changed
- Redesigned settings page with sidebar navigation and organized sections

## [1.1.0] - 2026-02-14

### Added - Complete WiFi Security Platform
- **WiFi Management UI** - Comprehensive web interface for all wireless features
  - 7 tabs: Overview, Client Mode, Access Point, Packet Capture, Site Survey, Wireless IDS, Client Tracking
  - Real-time status monitoring and controls
  - Network scanning and connection management
- **Auto-Update UI** - Software update management interface
  - Check for updates from GitHub releases
  - Download and install updates with progress tracking
  - View update history
  - One-click rollback to previous version
- **WiFi Access Point Mode** - Turn device into wireless hotspot
- **WiFi Packet Capture** - Monitor mode 802.11 frame capture
- **WiFi Site Survey** - Access point detection and analysis
- **Wireless IDS** - Rogue AP detection, known SSID whitelist
- **Client Tracking** - MAC tracking, vendor identification, probe analysis

### Backend Enhancements
- Added 25 new WiFi API endpoints across 6 feature categories
- Added 9 auto-update API endpoints
- New modules: `wifi_analyzer.py`, `github_client.py`, `update_manager.py`

## [1.0.1] - 2026-02-13

### Fixed
- Corrected duplicate function definitions in system monitor
- Fixed test imports and module dependencies
- Ensured all scripts have executable permissions
- Resolved health check file loading issues

### CI/CD
- Added GitHub Actions workflows (lint-and-test, test-startup, release)

## [1.0.0] - 2026-02-10

### Added
- **AI-Powered Anomaly Detection**: Volume anomalies, port/host scans, beaconing, DNS DGA/tunneling
- **AI Assistant**: On-device LLM integration via Ollama (TinyLLaMA)
- **AI Analysis Page**: Anomaly status, chat interface, sensitivity controls

### Fixed
- Fixed timezone bug in traffic statistics

## [0.3.0] - 2026-02-09

### Added
- **Packet Viewer**: In-browser packet inspection with protocol coloring
- **Display Filters**: Wireshark-style filtering
- **Stream Following**: TCP/UDP stream reconstruction
- Dark/light theme toggle

## [0.2.0] - 2026-02-08

### Added
- **Zeek Log Browser**: Navigate and search Zeek logs
- **Enhanced Statistics**: Connection trends, DNS analytics, service distribution
- **PCAP Filtering**: BPF filter builder with preview and download

## [0.1.0] - 2026-02-01

### Added
- Initial release
- SPAN and Bridge network modes
- Suricata IDS and Zeek integration
- tcpdump packet capture
- Web dashboard with real-time alerts
- Health check and storage management scripts
- Systemd service integration
