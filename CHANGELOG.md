# Changelog

All notable changes to NetworkTap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-02-06

### Added

- **Packet Viewer**: In-browser packet inspection (lightweight Wireshark alternative)
  - Paginated packet list with protocol coloring
  - Click any packet to view layer details and hex dump
  - Display filter support (Wireshark-style syntax)
  - TCP/UDP stream following with ASCII/hex view
  - Efficient on-demand parsing via tshark (no full PCAP loading)

- **New API Endpoints**:
  - `GET /api/pcaps/{filename}/packets` - Paginated packet list
  - `GET /api/pcaps/{filename}/packets/{frame}` - Packet detail with hex dump
  - `GET /api/pcaps/{filename}/streams` - List TCP/UDP streams
  - `GET /api/pcaps/{filename}/streams/{type}/{id}` - Follow stream content

### Changed

- PCAPs page now shows "View" button for in-browser packet inspection
- Updated version to 0.3.0

---

## [0.2.0] - 2026-02-06

### Added

- **Zeek Log Browser**: New page to browse, filter, and search Zeek logs
  - Support for conn, dns, http, ssl, files, notice, and weird log types
  - Tabbed interface with entry counts per log type
  - Filtering by IP, port, protocol, time range, and text search
  - Expandable row details with full entry metadata
  - Pagination with configurable items per page
  - Type-specific table renderers (DNS answers, HTTP status codes, SSL ciphers)

- **Enhanced Traffic Statistics**: Major expansion of the Statistics page
  - Connection trends line chart with interactive time range selector (6h/24h/3d/1w)
  - DNS analytics: top domains list, query type donut chart
  - Service distribution horizontal bar chart
  - Interactive chart tooltips showing exact values on hover

- **PCAP Filtering**: Filter packets before download
  - Visual BPF filter builder (source/dest IP, ports, protocol)
  - Raw BPF filter input for advanced users
  - Preview button showing matching packet count
  - Download filtered PCAP with only matching packets

- **UI Modernization**: Visual polish and improved UX
  - Smooth page transition animations
  - Card hover effects with lift and shadow
  - Skeleton loading states for all data sections
  - Animated number value transitions
  - Status dot pulse animation for online services
  - Global chart tooltip system
  - Reusable pagination component
  - Button ripple effects on click

- **New API Endpoints**:
  - `GET /api/zeek/logs` - List available Zeek log types
  - `GET /api/zeek/logs/{type}` - Paginated log entries with filters
  - `GET /api/zeek/logs/{type}/{uid}` - Single entry by UID
  - `POST /api/zeek/search` - Cross-log text search
  - `GET /api/zeek/stats/dns` - DNS statistics
  - `GET /api/zeek/stats/trends` - Connection count trends
  - `GET /api/zeek/stats/services` - Service distribution
  - `GET /api/stats/dns` - DNS statistics (alternate path)
  - `GET /api/stats/trends` - Connection trends (alternate path)
  - `GET /api/stats/services` - Service distribution (alternate path)
  - `GET /api/pcaps/{filename}/count` - Count packets matching filter
  - `GET /api/pcaps/{filename}/filter` - Download filtered PCAP

### Changed

- Statistics page completely redesigned with new chart sections
- PCAP browser now shows filter button alongside download
- Dashboard uses skeleton loading instead of spinners
- Improved responsive behavior for new components

## [0.1.0] - 2026-02-04

### Added

- **HTTPS/TLS Support**: Self-signed certificate generation, optional Let's Encrypt integration
- **Multi-user Authentication**: Role-based access control (admin/viewer), PBKDF2 password hashing
- **Traffic Statistics**: Bandwidth charts, protocol distribution, top talkers, top ports from Zeek data
- **PCAP Search/Preview**: Search packets by IP, port, protocol; view connection summaries
- **Suricata Rules Management**: Browse, search, enable/disable rules; threshold configuration; live reload
- **Backup & Restore**: Configuration backup/restore with automatic pre-restore snapshots
- **Syslog Forwarding**: Remote syslog/SIEM integration (UDP/TCP, syslog/JSON format)
- **Report Export**: CSV, HTML, and JSON report generation for alerts and statistics
- **Dark/Light Theme**: Toggle between dark and light themes with preference persistence
- **Mobile Responsive**: Improved touch targets, hamburger menu, responsive layouts

### Changed

- Updated web service to conditionally enable TLS based on configuration
- Enhanced authentication to support both config-based and multi-user modes
- Extended configuration file with TLS and syslog settings

## [0.0.1-beta] - 2026-02-04

### Added

- Initial beta release
- **Operating modes**: SPAN/mirror and inline transparent bridge
- **Packet capture**: tcpdump with time-based rotation, file limits, BPF filtering, and gzip compression
- **Suricata IDS**: af-packet capture, EVE JSON logging, community-id, automatic rule updates
- **Zeek IDS**: JSON logging, standard protocol analyzers, connection tracking, SSH brute-force detection
- **FastAPI web backend**: REST API for system status, capture control, alerts, configuration, and PCAP management
- **WebSocket**: Real-time Suricata alert streaming to the dashboard
- **Web dashboard**: Dark-themed SPA with six pages (Dashboard, Captures, Alerts, Network, PCAPs, Settings)
- **Dashboard page**: CPU/memory/disk/uptime stat cards, service status, traffic sparkline chart, recent alert feed
- **Capture management**: Start/stop controls via the web UI, recent file listing
- **Alerts page**: Combined Suricata and Zeek alerts with severity badges, source filtering, text search, auto-scroll
- **Network page**: Interface status cards with traffic counters, operating mode switcher
- **PCAP browser**: File listing with size/date, download with authentication, storage usage bar
- **Settings page**: Browser credential management, read-only server configuration display
- **Authentication**: HTTP Basic auth for all API endpoints
- **systemd services**: Units for capture, Suricata, Zeek, web dashboard, and hourly storage cleanup timer
- **Storage management**: Automatic pcap retention enforcement, emergency cleanup on low disk
- **Firewall hardening**: UFW rules scoped to management interface (SSH + web port only)
- **Health check script**: Validates services, interfaces, disk space, and memory
- **Installer**: Automated setup with NIC detection, dependency installation, and service deployment
- **Uninstaller**: Clean removal of services, units, and optionally data
- **Configuration**: Single config file (`networktap.conf`) for all settings
- **Documentation**: Setup guide with wiring diagrams, installation steps, and troubleshooting
