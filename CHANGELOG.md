# Changelog

All notable changes to NetworkTap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - WPA2-PSK security
  - DHCP server (dnsmasq)
  - Client tracking
  - Runtime start/stop/restart controls
  - Configuration management
- **WiFi Packet Capture** - Monitor mode 802.11 frame capture
  - Automatic monitor mode enablement
  - Channel selection
  - Rotating pcap files
  - Separate storage for wireless captures
- **WiFi Site Survey** - Access point detection and analysis
  - Signal strength analysis
  - Channel utilization mapping
  - Best channel recommendation
  - JSON export
- **Wireless IDS** - Intrusion detection for WiFi
  - Rogue AP detection
  - Known SSID whitelist
  - Hidden SSID detection
  - Alert management and history
- **Client Tracking** - Device inventory and analysis
  - MAC address tracking
  - Vendor identification (OUI lookup)
  - Probe request analysis
  - Active client monitoring
- **Auto-Update System** - Automated software updates
  - GitHub releases integration
  - SHA256 checksum verification
  - Automatic backup before update
  - Rollback capability
  - Update history tracking

### Backend Enhancements
- Added 25 new WiFi API endpoints across 6 feature categories
- Added 9 auto-update API endpoints
- New modules: `wifi_analyzer.py`, `github_client.py`, `update_manager.py`
- 5 new shell scripts for WiFi and update management
- Extended `routes_wifi.py` from 132 to 790 lines

### Testing
- 140+ tests executed across all new features
- 100% pass rate on component tests (105/105)
- 90% pass rate on comprehensive integration tests (45/50)
- 5 full end-to-end application test runs completed

### Documentation
- Added `DEPLOYMENT_READINESS.md` with comprehensive testing report
- Updated navigation with WiFi and Updates menu items
- Integrated all new features into help system

## [1.0.1] - 2026-02-13

### Fixed
- Corrected duplicate function definitions in system monitor
- Fixed test imports and module dependencies  
- Ensured all scripts have executable permissions
- Resolved health check file loading issues

### CI/CD
- Added GitHub Actions workflows (lint-and-test, test-startup, release)
- Automated testing on push and PR
- Automated release creation with changelog

## [1.0.0] - 2026-02-10

### Added

- **AI-Powered Anomaly Detection**: Lightweight statistical anomaly detection engine
  - Volume anomalies (sudden traffic spikes/drops)
  - Port scan detection (single source hitting multiple ports)
  - Host scan detection (single source hitting multiple hosts)
  - Beaconing detection (regular interval connections indicating C2)
  - DNS anomalies: DGA detection (high entropy domains), DNS tunneling (TXT queries)
  - Configurable sensitivity levels (low/medium/high)
  - Real-time anomaly feed on AI Analysis page

- **AI Assistant**: On-device LLM integration via Ollama
  - TinyLLaMA model optimized for 8GB RAM devices (Pi CM4)
  - Context-aware responses using recent alerts and traffic data
  - Natural language queries about network activity
  - Alert summarization and IP analysis
  - Toggle on/off to conserve resources

- **AI Analysis Page**: New dashboard page for AI features
  - Anomaly detection status and recent anomalies list
  - AI chat interface for network analysis questions
  - Sensitivity configuration controls

### Fixed
- Fixed timezone bug in traffic statistics where UTC timestamps were incorrectly compared with local time

### Changed
- Improved chart performance with data downsampling for time series with >100 points

## [0.3.0] - 2026-02-09

### Added
- **Packet Viewer**: In-browser packet inspection
  - Protocol coloring (TCP, UDP, ICMP, ARP, DNS, HTTP, TLS)
  - Layer details with expandable sections
  - Hex dump view
  - Packet navigation
  
- **Display Filters**: Wireshark-style filtering
  - Filter by protocol, IP, port, flags
  - Example filter library
  - Syntax validation

- **Stream Following**: TCP/UDP stream reconstruction
  - View full conversation content
  - ASCII and hex display modes
  - Client/server color coding

- **UI Improvements**
  - Dark/light theme toggle
  - Better mobile responsiveness
  - Faster page transitions

## [0.2.0] - 2026-02-08

### Added
- **Zeek Log Browser**: Navigate and search Zeek logs (conn, dns, http, ssl, files, notice, weird)
- **Enhanced Statistics**: Connection trends chart, DNS analytics, service distribution
- **PCAP Filtering**: BPF filter builder with preview and download
- **UI Modernization**: Page transitions, skeleton loading, animated values, hover effects

### Fixed
- PCAP download handling for large files
- Timestamp formatting in various views
- Service status polling edge cases

## [0.1.0] - 2026-02-01

### Added
- Initial release
- SPAN and Bridge network modes
- Suricata IDS integration
- Zeek network monitor integration
- tcpdump packet capture
- Web dashboard with real-time alerts
- Health check and storage management scripts
- Systemd service integration
