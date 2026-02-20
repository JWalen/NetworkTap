# NetworkTap

**v1.0.41**

Network tap and monitoring appliance for the OnLogic FR201/FR202 (2-NIC Linux platform). Provides passive packet capture, inline bridging, IDS/IPS via Suricata and Zeek, AI-powered anomaly detection, and a modern web dashboard for administration.

## Features

- **Dual operating modes**: SPAN/mirror (passive monitoring) and inline transparent bridge
- **Packet capture**: tcpdump with automatic rotation, compression, and retention management
- **IDS/IPS**: Suricata (signature-based) and Zeek (connection logging and protocol analysis)
- **AI Anomaly Detection**: Lightweight on-device detection of traffic anomalies, port scans, beaconing, and DNS threats
- **AI Assistant**: On-device LLM (TinyLLaMA via Ollama) for natural language network analysis
- **Web dashboard**: Dark-themed SPA with real-time alerts via WebSocket, system monitoring, capture control, and PCAP downloads
- **FR202 Front Panel Display**: 5-page touch-navigable status display on the 3.5" ST7789V TFT with auto-dimming backlight
- **Zeek Log Browser**: Browse, filter, and search Zeek logs (conn, dns, http, ssl, files, notice, weird)
- **Traffic Statistics**: Connection trends, DNS analytics, service distribution, protocol breakdown
- **Packet Viewer**: In-browser packet inspection with display filters and stream following
- **PCAP Filtering**: Filter and preview packets before download using BPF expressions
- **Service management**: systemd units for all daemons with automatic cleanup timers
- **Firewall hardening**: UFW rules scoped to management interface
- **OTA Updates**: Check for and install updates from GitHub releases with automatic backup and rollback

## Supported Hardware

| Platform | Description |
|----------|-------------|
| **OnLogic FR201** | 2-NIC Raspberry Pi CM4 appliance (headless) |
| **OnLogic FR202** | 2-NIC Raspberry Pi CM4 appliance with 3.5" front panel touchscreen, DIO, and ADC |

The FR202 front panel display shows system status across 5 touch-navigable pages:
1. **Dashboard** - Mode, IP, CPU/MEM/DISK bars, service status, alert & PCAP counts
2. **Network** - All interfaces with IP, state, speed, and MAC
3. **Services** - All services with status, sub-state, and uptime
4. **Alerts** - Total events, severity breakdown, top alert signatures
5. **System** - Hostname, uptime, CPU temp, kernel, storage details, version

## Quick Start

```bash
# Clone the repository
git clone <repository-url> NetworkTap
cd NetworkTap

# Run the installer (requires root, Debian/Ubuntu)
sudo bash install.sh

# Access the web UI
# http://<management-ip>:8443
# Default credentials: admin / networktap
```

## Architecture

```
+---------------------------------------------+
|            FR201/FR202 Appliance             |
|                                              |
|  NIC1 (capture) --+                         |
|                    +- tcpdump  (pcap)        |
|                    +- Suricata (IDS alerts)  |
|                    +- Zeek     (conn logs)   |
|                                              |
|  NIC2 (management) -- FastAPI Web Dashboard  |
|                                              |
|  FR202 Display -- ST7789V 320x240 TFT       |
|    SPI3, touch via ST1633i on I2C5           |
+----------------------------------------------+
```

### SPAN Mode

NIC1 connects to a switch SPAN/mirror port for passive traffic monitoring. NIC2 provides management access (SSH, Web UI).

### Bridge Mode

Both NICs form a transparent Layer 2 bridge. Traffic passes through the appliance inline. Management is via the bridge IP.

## Project Structure

```
NetworkTap/
├── install.sh                # Master installer
├── uninstall.sh              # Clean removal
├── networktap.conf           # Main configuration
├── setup/                    # Installation scripts
│   ├── configure_display.sh  # FR202 display & touch setup
│   └── ...
├── config/                   # Suricata, Zeek, logrotate configs
├── services/                 # systemd unit files
├── scripts/
│   ├── display_status.py     # FR202 front panel display daemon
│   ├── update.sh             # OTA update script
│   └── ...
├── web/
│   ├── app.py                # FastAPI application
│   ├── api/                  # REST API routes
│   ├── core/                 # Backend modules
│   ├── static/               # CSS, JS, images
│   └── templates/            # HTML shell
└── docs/
    └── SETUP.md              # Detailed setup guide
```

## Web Dashboard

The dashboard is a single-page application with a dark theme, accessible at `http://<management-ip>:8443`.

| Page | Description |
|------|-------------|
| **Dashboard** | System stats (CPU, memory, disk, uptime), service status, network throughput charts, recent alerts |
| **Captures** | Start/stop packet capture, view active captures and recent files |
| **Alerts** | Real-time IDS alerts from Suricata and Zeek with severity filtering |
| **AI Analysis** | Anomaly detection results, AI assistant chat, feature toggles |
| **Network** | Interface status, operating mode switcher |
| **WiFi** | WiFi client/AP mode, packet capture, site survey, wireless IDS, client tracking |
| **PCAPs** | Browse and download capture files with filtering, storage usage |
| **Statistics** | Traffic analytics, connection trends, DNS stats, service distribution |
| **Zeek Logs** | Browse and search Zeek logs with type-specific views |
| **Rules** | Suricata rule management |
| **Terminal** | Web-based terminal with command whitelist |
| **Updates** | Check for and install OTA updates with rollback |
| **Settings** | Configuration overview, credential management |

---

## FR202 Front Panel Display

The OnLogic FR202's 3.5" ST7789V TFT display is used to show system status without needing to access the web UI.

### Hardware Configuration

| Component | Detail |
|-----------|--------|
| Display IC | ST7789V 320x240 |
| Bus | SPI3 (port=3, cs=0) |
| DC Pin | GPIO 16 |
| Reset Pin | GPIO 27 (open-drain) |
| SPI Mode | 3 |
| Rotation | 180 degrees |
| Backlight | I2C expander at 0x3C on I2C bus 1 |
| Touch IC | ST1633i at 0x70 on I2C bus 5 |
| Touch Interrupt | GPIO 26 |

### config.txt Requirements (FR202)

```
dtparam=i2c_arm=on
#dtparam=spi=on
dtoverlay=i2c1,pins_44_45
dtoverlay=spi3-1cs,cs0_pin=24
dtoverlay=spi4-1cs
dtoverlay=i2c5,pins12_13=on,baudrate=40000
```

**Note:** Generic `dtparam=spi=on` must be **commented out** per OnLogic documentation. The FR202 uses specific SPI3/SPI4 overlays instead.

### Touch Navigation

- Tap the screen to cycle through pages
- Backlight auto-dims after 2 minutes idle
- First tap on a dimmed screen wakes it without changing page

---

## Zeek Log Browser

The Zeek Logs page (`#zeek`) provides a powerful interface to browse and search Zeek's JSON logs.

### Supported Log Types

| Log Type | Description |
|----------|-------------|
| **conn** | Connection summaries with duration, bytes, packets |
| **dns** | DNS queries and responses with answers |
| **http** | HTTP requests with method, host, URI, status |
| **ssl** | SSL/TLS connections with SNI, cipher, version |
| **files** | File transfers with MIME type, size, hashes |
| **notice** | Zeek notices and alerts |
| **weird** | Unusual/unexpected protocol behavior |

### Filtering Options

- **IP Address**: Filter by source or destination IP (partial match)
- **Port**: Filter by source or destination port
- **Protocol**: Filter by TCP, UDP, or ICMP
- **Time Range**: Limit to last hour, 6 hours, 24 hours, 3 days, or week
- **Text Search**: Full-text search across all fields

---

## Traffic Statistics

The Statistics page (`#stats`) provides comprehensive traffic analytics.

### Connection Trends

Interactive line chart showing connection counts over time with selectable ranges (6h, 24h, 3d, 1w).

### DNS Analytics

- **Top Domains**: Most frequently queried domains
- **Query Types**: Distribution of A, AAAA, MX, TXT, etc.
- **Response Codes**: Success vs. NXDOMAIN vs. errors

### Service Distribution

Horizontal bar chart showing traffic distribution by detected service (HTTP, DNS, SSH, etc.).

### Protocol & Top Talkers

- Protocol distribution (TCP/UDP/ICMP breakdown)
- Top source IPs by traffic volume

---

## Packet Viewer

The PCAPs page (`#pcaps`) includes a lightweight in-browser packet viewer.

### Features

- **Packet List**: Paginated view of all packets with protocol coloring
- **Packet Details**: Click any packet to see layer-by-layer decode and hex dump
- **Display Filters**: Filter packets using Wireshark-style syntax
- **Stream Following**: View TCP/UDP stream content in ASCII or hex

### Display Filter Examples

```
tcp.port == 443
http
ip.addr == 192.168.1.100
dns
tls.handshake
```

---

## AI Features

NetworkTap includes on-device AI capabilities optimized for resource-constrained devices like the Raspberry Pi CM4 (8GB RAM).

### Anomaly Detection

Lightweight statistical analysis that runs continuously to detect:

| Anomaly Type | Description |
|--------------|-------------|
| **Volume Anomaly** | Sudden spikes or drops in traffic volume |
| **Port Scan** | Single source probing multiple ports |
| **Host Scan** | Single source probing multiple hosts |
| **Beaconing** | Regular interval connections (C2 indicator) |
| **DNS DGA** | High-entropy domain names (malware indicator) |
| **DNS Tunneling** | Excessive TXT queries (data exfiltration) |

### AI Assistant

Natural language interface powered by TinyLLaMA (via Ollama). Ask questions like:
- "What unusual activity happened in the last hour?"
- "Summarize the recent alerts"
- "What can you tell me about IP 192.168.1.100?"

---

## Configuration

Edit `/etc/networktap.conf` to change settings.

Key options:

| Setting | Default | Description |
|---------|---------|-------------|
| `MODE` | `span` | `span` or `bridge` |
| `NIC1` / `NIC2` | `eth0` / `eth1` | Network interfaces |
| `WEB_PORT` | `8443` | Dashboard port |
| `WEB_USER` / `WEB_PASS` | `admin` / `networktap` | Dashboard credentials |
| `CAPTURE_ROTATE_SECONDS` | `3600` | Pcap rotation interval |
| `RETENTION_DAYS` | `7` | Pcap retention period |
| `SURICATA_ENABLED` | `yes` | Enable Suricata IDS |
| `ZEEK_ENABLED` | `yes` | Enable Zeek |
| `ANOMALY_DETECTION_ENABLED` | `yes` | Enable AI anomaly detection |
| `AI_ASSISTANT_ENABLED` | `yes` | Enable AI assistant |

After editing, restart services:

```bash
sudo systemctl restart networktap-web
```

## Service Management

```bash
# Check all services
systemctl status networktap-*

# Start/stop capture
sudo systemctl start networktap-capture
sudo systemctl stop networktap-capture

# View logs
journalctl -u networktap-web -f
journalctl -u networktap-display -f

# Health check
sudo /opt/networktap/scripts/health_check.sh

# Switch operating mode
sudo /opt/networktap/scripts/switch_mode.sh bridge
```

## Requirements

- OnLogic FR201 or FR202 (Raspberry Pi CM4)
- Debian 12 / Ubuntu 22.04+ / Raspberry Pi OS (Bookworm)
- 2 Ethernet NICs
- 4 GB RAM minimum (8 GB recommended)
- 120 GB+ storage for packet captures
- Root access for installation

## Uninstall

```bash
sudo bash /opt/networktap/uninstall.sh
```

## License

See LICENSE file for details.
