# NetworkTap

**v1.0.0**

Network tap and monitoring appliance for the OnLogic FR201 (2-NIC Linux platform). Provides passive packet capture, inline bridging, IDS/IPS via Suricata and Zeek, AI-powered anomaly detection, and a modern web dashboard for administration.

## Features

- **Dual operating modes**: SPAN/mirror (passive monitoring) and inline transparent bridge
- **Packet capture**: tcpdump with automatic rotation, compression, and retention management
- **IDS/IPS**: Suricata (signature-based) and Zeek (connection logging and protocol analysis)
- **AI Anomaly Detection**: Lightweight on-device detection of traffic anomalies, port scans, beaconing, and DNS threats
- **AI Assistant**: On-device LLM (TinyLLaMA via Ollama) for natural language network analysis
- **Web dashboard**: Dark-themed SPA with real-time alerts via WebSocket, system monitoring, capture control, and PCAP downloads
- **Zeek Log Browser**: Browse, filter, and search Zeek logs (conn, dns, http, ssl, files, notice, weird)
- **Traffic Statistics**: Connection trends, DNS analytics, service distribution, protocol breakdown
- **Packet Viewer**: In-browser packet inspection with display filters and stream following
- **PCAP Filtering**: Filter and preview packets before download using BPF expressions
- **Service management**: systemd units for all daemons with automatic cleanup timers
- **Firewall hardening**: UFW rules scoped to management interface

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
┌─────────────────────────────────────────────┐
│                  FR201 Appliance             │
│                                             │
│  NIC1 (capture) ──┐                        │
│                    ├─ tcpdump  (pcap)       │
│                    ├─ Suricata (IDS alerts) │
│                    └─ Zeek     (conn logs)  │
│                                             │
│  NIC2 (management) ── FastAPI Web Dashboard │
└─────────────────────────────────────────────┘
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
├── config/                   # Suricata, Zeek, logrotate configs
├── services/                 # systemd unit files
├── scripts/                  # Operational scripts
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
| **PCAPs** | Browse and download capture files with filtering, storage usage |
| **Statistics** | Traffic analytics, connection trends, DNS stats, service distribution |
| **Zeek Logs** | Browse and search Zeek logs with type-specific views |
| **Rules** | Suricata rule management |
| **Settings** | Configuration overview, browser credential management |

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

### Expandable Details

Click any row to expand and see full entry details including:
- Connection UID for correlation across logs
- Complete byte/packet counts
- Protocol-specific metadata (DNS answers, HTTP headers, SSL certs)

---

## Traffic Statistics

The Statistics page (`#stats`) provides comprehensive traffic analytics.

### Connection Trends

Interactive line chart showing connection counts over time with selectable ranges:
- 6 hours, 24 hours, 3 days, 1 week

Hover over points to see exact values.

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

### How to Use

1. Click the **View** button next to any PCAP file
2. Browse packets in the paginated list
3. Click any row to see full packet details
4. Use the filter box for display filters (e.g., `tcp.port == 443`)
5. Click **Streams** to see TCP/UDP conversations

### Display Filter Examples

```
# TCP port 443
tcp.port == 443

# HTTP traffic
http

# Specific IP
ip.addr == 192.168.1.100

# DNS queries
dns

# TLS handshakes
tls.handshake
```

### Resource Usage

The packet viewer parses on-demand using tshark, never loading the entire PCAP into memory. Safe for large captures on 8GB systems.

---

## PCAP Filtering

The PCAPs page (`#pcaps`) also includes packet filtering before download.

### How to Use

1. Click the **filter icon** next to any PCAP file
2. Enter filter criteria:
   - **Source IP**: e.g., `192.168.1.100`
   - **Destination IP**: e.g., `10.0.0.1`
   - **Source/Dest Port**: e.g., `443`
   - **Protocol**: TCP, UDP, ICMP, ARP
   - **Raw BPF**: e.g., `tcp port 443 and host 192.168.1.1`
3. Click **Preview** to see how many packets match
4. Click **Download Filtered** to get only matching packets

### BPF Filter Examples

```
# All TCP traffic on port 443
tcp port 443

# Traffic to/from a specific host
host 192.168.1.100

# HTTP traffic only
tcp port 80 or tcp port 8080

# DNS queries
udp port 53

# Specific conversation
host 192.168.1.1 and host 10.0.0.1
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

Configure sensitivity in `/etc/networktap.conf`:
- `low` - Fewer false positives, may miss subtle anomalies
- `medium` - Balanced (default)
- `high` - More sensitive, may have more false positives

### AI Assistant

Natural language interface powered by TinyLLaMA (via Ollama). Ask questions like:
- "What unusual activity happened in the last hour?"
- "Summarize the recent alerts"
- "What can you tell me about IP 192.168.1.100?"

The assistant has context about recent alerts, traffic statistics, and detected anomalies.

### Resource Usage

- **Anomaly Detection**: ~50MB RAM, runs every 60 seconds
- **AI Assistant**: ~1.5GB RAM when active (model loaded on-demand)
- Both features can be toggled on/off via the web UI or config file

---

## Configuration

Edit `/etc/networktap.conf` (or `/opt/networktap/networktap.conf`) to change settings.

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
| `ANOMALY_SENSITIVITY` | `medium` | Detection sensitivity (low/medium/high) |
| `AI_ASSISTANT_ENABLED` | `yes` | Enable AI assistant |
| `OLLAMA_MODEL` | `tinyllama` | LLM model for AI assistant |

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

# Health check
sudo /opt/networktap/scripts/health_check.sh

# Switch operating mode
sudo /opt/networktap/scripts/switch_mode.sh bridge
```

## Requirements

- Debian 12 / Ubuntu 22.04+
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
