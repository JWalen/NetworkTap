# NetworkTap Setup Guide

## Hardware: OnLogic FR201

The OnLogic FR201 is a fanless industrial PC with 2 Ethernet NICs, suitable for deployment as a network tap appliance.

### Hardware Requirements
- OnLogic FR201 (or compatible 2-NIC Linux system)
- 2x Ethernet NICs (Intel recommended)
- Minimum 4GB RAM (8GB recommended)
- 120GB+ SSD for pcap storage
- Debian 12 / Ubuntu 22.04+ installed

---

## Network Wiring

### SPAN / Mirror Mode
```
                    ┌──────────────┐
  Switch SPAN Port ─┤ NIC1 (eth0)  │
                    │   FR201      │
  Management LAN  ──┤ NIC2 (eth1)  │
                    └──────────────┘
```
- **NIC1** connects to the switch SPAN/mirror port (receive-only traffic copy)
- **NIC2** connects to the management network for SSH and Web UI access
- NIC1 runs in promiscuous mode with no IP address
- NIC2 gets an IP via DHCP or static configuration

### Inline Bridge Mode
```
                    ┌──────────────┐
  Network Segment ──┤ NIC1 (eth0)  │
       A            │   FR201      │
  Network Segment ──┤ NIC2 (eth1)  │
       B            └──────────────┘
```
- Both NICs are bridged transparently (Layer 2)
- Traffic passes through the appliance between segments
- Management access is via the bridge IP address
- If the appliance fails, the link goes down (consider a bypass switch)

---

## Installation

### 1. Prepare the System
```bash
# Start with a fresh Debian/Ubuntu installation
sudo apt update && sudo apt upgrade -y

# Clone or copy the NetworkTap files
cd /tmp
git clone <repository-url> NetworkTap
cd NetworkTap
```

### 2. Run the Installer
```bash
sudo bash install.sh
```

The installer will:
1. Detect network interfaces
2. Install dependencies (tcpdump, Suricata, Zeek, Python)
3. Configure network interfaces for the selected mode
4. Deploy Suricata and Zeek configurations
5. Set up packet capture directories
6. Configure the firewall
7. Install and start all systemd services

### 3. Verify Installation
```bash
# Check all services
systemctl status networktap-*

# Run health check
sudo /opt/networktap/scripts/health_check.sh

# Access the web UI
# Open http://<management-ip>:8443 in a browser
```

---

## Configuration

The main configuration file is `/etc/networktap.conf` (symlinked from `/opt/networktap/networktap.conf`).

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `MODE` | `span` | Operating mode: `span` or `bridge` |
| `NIC1` | `eth0` | First NIC (capture in SPAN, bridge member) |
| `NIC2` | `eth1` | Second NIC (management in SPAN, bridge member) |
| `WEB_PORT` | `8443` | Web dashboard port |
| `WEB_USER` | `admin` | Dashboard username |
| `WEB_PASS` | `networktap` | Dashboard password (change this!) |
| `CAPTURE_ROTATE_SECONDS` | `3600` | New pcap file every N seconds |
| `RETENTION_DAYS` | `7` | Delete pcaps older than this |

### Changing the Operating Mode
```bash
# Switch to bridge mode
sudo /opt/networktap/scripts/switch_mode.sh bridge

# Switch to SPAN mode
sudo /opt/networktap/scripts/switch_mode.sh span
```

Or use the web dashboard: Network > Mode Switcher.

---

## Web Dashboard

Access at `http://<management-ip>:8443`

Default credentials: `admin` / `networktap`

### Pages
- **Dashboard**: System stats, service status, traffic chart, recent alerts
- **Captures**: Start/stop packet capture, view recent files
- **Alerts**: Real-time IDS alerts from Suricata and Zeek
- **Network**: Interface status, mode switching
- **PCAPs**: Browse and download capture files
- **Settings**: View configuration, manage browser credentials

### Real-time Alerts
The alerts page connects via WebSocket for live alert streaming. New Suricata alerts appear automatically without refreshing.

---

## Service Management

```bash
# Start/stop capture
sudo systemctl start networktap-capture
sudo systemctl stop networktap-capture

# Restart the web dashboard
sudo systemctl restart networktap-web

# View logs
journalctl -u networktap-web -f
journalctl -u networktap-suricata -f

# Check all NetworkTap services
systemctl list-units 'networktap-*'
```

---

## Storage Management

Pcap files are stored in `/var/lib/networktap/captures/`.

- **Automatic cleanup**: The `networktap-cleanup.timer` runs hourly to delete files older than `RETENTION_DAYS`
- **Emergency cleanup**: If disk falls below `MIN_FREE_DISK_PCT`, oldest files are deleted immediately
- **Manual cleanup**: `sudo /opt/networktap/scripts/storage_cleanup.sh`

---

## Uninstallation

```bash
sudo bash /opt/networktap/uninstall.sh
```

This stops all services, removes systemd units, and deletes the installation. Optionally removes capture data and logs. Does not remove Suricata/Zeek system packages.

---

## Troubleshooting

### Services won't start
```bash
# Check service logs
journalctl -u networktap-web --no-pager -n 50
journalctl -u networktap-suricata --no-pager -n 50

# Verify the config file
cat /etc/networktap.conf

# Run the health check
sudo /opt/networktap/scripts/health_check.sh
```

### No traffic captured
1. Verify the capture interface is correct: `ip link show`
2. Check promiscuous mode: `ip link show eth0 | grep PROMISC`
3. Verify SPAN port is configured on the switch
4. Try a manual capture: `sudo tcpdump -i eth0 -c 10`

### Web UI not accessible
1. Check the service: `systemctl status networktap-web`
2. Check the firewall: `sudo ufw status`
3. Verify the port: `ss -tlnp | grep 8443`

### Suricata not generating alerts
1. Check if Suricata is running: `systemctl status networktap-suricata`
2. Check the EVE log: `tail -f /var/log/suricata/eve.json`
3. Verify rules are loaded: `suricata -T -c /etc/suricata/suricata.yaml`
4. Update rules: `sudo suricata-update`
