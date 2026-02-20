#!/usr/bin/env python3
"""NetworkTap Front Panel Display - FR202 ST7789V 3.5" 320x240 TFT

Multi-page status display with touch navigation for the OnLogic FR202.
Tap anywhere on the screen to cycle to the next page.

FR202 Display Configuration (from OnLogic reference):
  - ST7789V on SPI3 (port=3, cs=0, dc=GPIO16, rst=GPIO27 open-drain)
  - SPI mode 3, rotation 180, 60MHz
  - Backlight via I2C expander at 0x3C on I2C bus 1
  - Touch controller ST1633i at 0x70 on I2C bus 5, interrupt GPIO 26

Pages:
  1. Dashboard  - mode, IP, CPU/MEM/DISK, services, alerts/pcaps
  2. Network    - interface details, IPs, link speeds
  3. Services   - all service statuses with uptime
  4. Alerts     - recent alert counts and top signatures
  5. System     - hostname, uptime, CPU temp, kernel, storage
"""

import os
import sys
import time
import signal
import subprocess
import logging
import socket

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("display")

# Display dimensions
WIDTH = 320
HEIGHT = 240

# Defaults (overridden by config file)
REFRESH_INTERVAL = 5  # seconds
BACKLIGHT_TIMEOUT = 120  # seconds before dimming
DEFAULT_PAGE = "dashboard"

# Colors (RGB tuples)
BG = (13, 17, 23)
TEXT = (230, 237, 243)
DIM = (125, 133, 144)
ACCENT = (0, 212, 170)  # #00d4aa
GREEN = (63, 185, 80)
RED = (248, 81, 73)
YELLOW = (210, 153, 34)
BLUE = (56, 132, 244)
BAR_BG = (33, 38, 45)
DIVIDER = (48, 54, 61)
PAGE_DOT_ACTIVE = ACCENT
PAGE_DOT_INACTIVE = (48, 54, 61)

# Config path
CONF_PATH = "/etc/networktap.conf"
CONF_FALLBACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "networktap.conf")

# Page names
PAGES = ["dashboard", "network", "services", "alerts", "system"]

# Touch controller registers (ST1633i)
ST1633_REG = {
    "status": 0x01,
    "control": 0x02,
    "xy0_hi": 0x12,
    "x0_low": 0x13,
    "y0_low": 0x14,
}

# ─── Data Collection ────────────────────────────────────────────────


def load_config():
    """Parse shell-style KEY=VALUE config file."""
    conf = {}
    path = CONF_PATH if os.path.exists(CONF_PATH) else CONF_FALLBACK
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    conf[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return conf


def get_management_ip(conf):
    """Get the management interface IP address."""
    mode = conf.get("MODE", "span")
    if mode == "bridge":
        iface = conf.get("BRIDGE_NAME", "br0")
    else:
        iface = conf.get("NIC2", "eth1")

    try:
        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", iface],
            capture_output=True, text=True, timeout=5,
        )
        for line in out.stdout.strip().splitlines():
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "inet" and i + 1 < len(parts):
                    return parts[i + 1].split("/")[0]
    except Exception:
        pass
    return None


def check_service(name):
    """Check if a systemd service is active. Returns (active, sub_state)."""
    try:
        result = subprocess.run(
            ["systemctl", "show", name, "--property=ActiveState,SubState", "--no-pager"],
            capture_output=True, text=True, timeout=5,
        )
        info = {}
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                info[k] = v
        active = info.get("ActiveState", "unknown") == "active"
        sub = info.get("SubState", "unknown")
        return active, sub
    except Exception:
        return False, "unknown"


def get_service_uptime(name):
    """Get how long a service has been running."""
    try:
        result = subprocess.run(
            ["systemctl", "show", name, "--property=ActiveEnterTimestamp", "--no-pager"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            if "ActiveEnterTimestamp=" in line:
                ts = line.split("=", 1)[1].strip()
                if not ts:
                    return None
                # Parse systemd timestamp
                from datetime import datetime
                # Format: "Wed 2025-01-15 10:30:00 UTC"
                for fmt in ["%a %Y-%m-%d %H:%M:%S %Z", "%a %Y-%m-%d %H:%M:%S %z"]:
                    try:
                        dt = datetime.strptime(ts, fmt)
                        delta = datetime.now(dt.tzinfo) - dt if dt.tzinfo else datetime.now() - dt
                        secs = int(delta.total_seconds())
                        if secs < 0:
                            return None
                        if secs < 60:
                            return f"{secs}s"
                        if secs < 3600:
                            return f"{secs // 60}m"
                        if secs < 86400:
                            return f"{secs // 3600}h{(secs % 3600) // 60}m"
                        return f"{secs // 86400}d{(secs % 86400) // 3600}h"
                    except ValueError:
                        continue
    except Exception:
        pass
    return None


def get_cpu_percent():
    """Read CPU usage from /proc/stat (avoids psutil dependency)."""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        idle = int(parts[4])
        total = sum(int(x) for x in parts[1:])
        if not hasattr(get_cpu_percent, "_prev"):
            get_cpu_percent._prev = (idle, total)
            time.sleep(0.1)
            return get_cpu_percent()
        prev_idle, prev_total = get_cpu_percent._prev
        get_cpu_percent._prev = (idle, total)
        d_idle = idle - prev_idle
        d_total = total - prev_total
        if d_total == 0:
            return 0
        return int(100 * (1 - d_idle / d_total))
    except Exception:
        return 0


def get_memory_info():
    """Read memory usage from /proc/meminfo. Returns (percent, used_mb, total_mb)."""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 1)
        avail = info.get("MemAvailable", total)
        pct = int(100 * (1 - avail / total))
        total_mb = total // 1024
        used_mb = (total - avail) // 1024
        return pct, used_mb, total_mb
    except Exception:
        return 0, 0, 0


def get_disk_info(path="/var/lib/networktap/captures"):
    """Get disk usage. Returns (percent, used_gb, total_gb)."""
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        if total == 0:
            return 0, 0, 0
        pct = int(100 * (1 - free / total))
        return pct, used / (1024**3), total / (1024**3)
    except Exception:
        return 0, 0, 0


def count_pcaps(capture_dir="/var/lib/networktap/captures"):
    """Count .pcap files and total size in capture directory."""
    count = 0
    total_size = 0
    try:
        for f in os.listdir(capture_dir):
            if ".pcap" in f:
                count += 1
                try:
                    total_size += os.path.getsize(os.path.join(capture_dir, f))
                except OSError:
                    pass
    except Exception:
        pass
    return count, total_size


def count_alerts(eve_path="/var/log/suricata/eve.json"):
    """Estimate alert count from eve.json line count (fast)."""
    try:
        result = subprocess.run(
            ["wc", "-l", eve_path],
            capture_output=True, text=True, timeout=5,
        )
        return int(result.stdout.strip().split()[0])
    except Exception:
        return 0


def get_interface_info():
    """Get details for all physical network interfaces."""
    interfaces = []
    try:
        result = subprocess.run(
            ["ip", "-j", "addr", "show"],
            capture_output=True, text=True, timeout=5,
        )
        import json
        data = json.loads(result.stdout)
        for iface in data:
            name = iface.get("ifname", "")
            if name == "lo":
                continue
            info = {"name": name, "state": iface.get("operstate", "UNKNOWN"), "ips": [], "mac": ""}
            for addr in iface.get("addr_info", []):
                if addr.get("family") == "inet":
                    info["ips"].append(addr.get("local", ""))
            # Get MAC
            if iface.get("address"):
                info["mac"] = iface["address"]
            # Get speed
            try:
                with open(f"/sys/class/net/{name}/speed") as f:
                    info["speed"] = f.read().strip() + " Mbps"
            except (OSError, IOError):
                info["speed"] = ""
            interfaces.append(info)
    except Exception:
        pass
    return interfaces


def get_uptime():
    """Get system uptime as a formatted string."""
    try:
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        days = secs // 86400
        hours = (secs % 86400) // 3600
        mins = (secs % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h {mins}m"
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"
    except Exception:
        return "?"


def get_cpu_temp():
    """Get CPU temperature."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp = int(f.read().strip()) / 1000
        return f"{temp:.1f}C"
    except Exception:
        return "?"


def get_kernel_version():
    """Get short kernel version."""
    try:
        with open("/proc/version") as f:
            parts = f.read().split()
            if len(parts) >= 3:
                return parts[2]
    except Exception:
        pass
    return "?"


def get_load_average():
    """Get 1-minute load average."""
    try:
        with open("/proc/loadavg") as f:
            return f.read().split()[0]
    except Exception:
        return "?"


def get_version():
    """Get NetworkTap version."""
    for path in ["/opt/networktap/VERSION",
                 os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")]:
        try:
            with open(path) as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return "?"


def get_recent_alert_sigs(eve_path="/var/log/suricata/eve.json", max_lines=200):
    """Read recent alert signatures from eve.json tail."""
    sigs = {}
    severities = {1: 0, 2: 0, 3: 0}  # severity -> count
    try:
        result = subprocess.run(
            ["tail", "-n", str(max_lines), eve_path],
            capture_output=True, text=True, timeout=5,
        )
        import json
        for line in result.stdout.strip().splitlines():
            try:
                entry = json.loads(line)
                if entry.get("event_type") == "alert":
                    alert = entry.get("alert", {})
                    sig = alert.get("signature", "Unknown")
                    sev = alert.get("severity", 3)
                    sigs[sig] = sigs.get(sig, 0) + 1
                    if sev in severities:
                        severities[sev] += 1
            except (json.JSONDecodeError, KeyError):
                continue
    except Exception:
        pass
    # Sort by count descending
    top = sorted(sigs.items(), key=lambda x: -x[1])[:5]
    return top, severities


# ─── Page Renderers ─────────────────────────────────────────────────


def draw_header(draw, font, font_sm, title, page_idx):
    """Draw common header with title, page dots, and time."""
    y = 4

    # Title
    draw.text((10, y), title, fill=ACCENT, font=font)

    # Page indicator dots
    dot_y = y + 7
    total_dots_w = len(PAGES) * 12 - 4
    dot_start_x = WIDTH - 10 - total_dots_w
    for i in range(len(PAGES)):
        cx = dot_start_x + i * 12
        color = PAGE_DOT_ACTIVE if i == page_idx else PAGE_DOT_INACTIVE
        draw.ellipse([cx - 3, dot_y - 3, cx + 3, dot_y + 3], fill=color)

    y += 18
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    return y + 5


def draw_footer(draw, font_sm, conf):
    """Draw common footer with time and port."""
    y = HEIGHT - 16
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 3
    now = time.strftime("%H:%M:%S")
    port = conf.get("WEB_PORT", "8443")
    draw.text((10, y), f":{port}", fill=DIM, font=font_sm)
    draw.text((WIDTH // 2, y), "tap to switch", fill=DIVIDER, font=font_sm, anchor="ma")
    draw.text((WIDTH - 10, y), now, fill=DIM, font=font_sm, anchor="ra")


def render_dashboard(draw, font, font_sm, conf):
    """Page 1: Dashboard overview."""
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=BG)

    y = draw_header(draw, font, font_sm, "Dashboard", 0)

    mode = conf.get("MODE", "span").upper()
    ip = get_management_ip(conf) or "No IP"
    cpu = get_cpu_percent()
    mem_pct, _, _ = get_memory_info()
    capture_dir = conf.get("CAPTURE_DIR", "/var/lib/networktap/captures")
    disk_pct, _, _ = get_disk_info(capture_dir)
    eve_path = conf.get("SURICATA_EVE_LOG", "/var/log/suricata/eve.json")

    # Mode + IP row
    draw.text((10, y), "MODE", fill=DIM, font=font_sm)
    draw.text((52, y), mode, fill=TEXT, font=font)
    draw.text((WIDTH - 10, y), ip, fill=TEXT, font=font, anchor="ra")
    y += 18

    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 6

    # Resource bars
    bar_x = 52
    bar_w = WIDTH - bar_x - 42
    bar_h = 13

    for label, pct, color in [("CPU", cpu, ACCENT), ("MEM", mem_pct, ACCENT),
                               ("DISK", disk_pct, YELLOW if disk_pct > 80 else ACCENT)]:
        draw.text((10, y), label, fill=DIM, font=font_sm)
        draw.rectangle([bar_x, y + 1, bar_x + bar_w, y + bar_h], fill=BAR_BG)
        fill_w = max(1, int(bar_w * pct / 100))
        if pct > 0:
            draw.rectangle([bar_x, y + 1, bar_x + fill_w, y + bar_h], fill=color)
        draw.text((WIDTH - 10, y + 1), f"{pct}%", fill=TEXT, font=font_sm, anchor="ra")
        y += bar_h + 5

    y += 2
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 6

    # Services (2x2 grid)
    draw.text((10, y), "SERVICES", fill=DIM, font=font_sm)
    y += 14

    services = [
        ("Capture", "networktap-capture"),
        ("Suricata", "networktap-suricata"),
        ("Zeek", "networktap-zeek"),
        ("Web UI", "networktap-web"),
    ]
    for i, (label, svc_name) in enumerate(services):
        col = 10 if i % 2 == 0 else WIDTH // 2 + 5
        row_y = y + (i // 2) * 18
        active, _ = check_service(svc_name)
        dot_color = GREEN if active else RED
        cx, cy = col + 5, row_y + 6
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=dot_color)
        draw.text((col + 13, row_y), label, fill=TEXT, font=font_sm)

    y += 38
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 6

    # Stats row
    alerts = count_alerts(eve_path)
    pcap_count, _ = count_pcaps(capture_dir)
    draw.text((10, y), "Alerts", fill=DIM, font=font_sm)
    draw.text((52, y), str(alerts), fill=TEXT, font=font)
    draw.text((WIDTH // 2 + 5, y), "PCAPs", fill=DIM, font=font_sm)
    draw.text((WIDTH // 2 + 48, y), str(pcap_count), fill=TEXT, font=font)

    draw_footer(draw, font_sm, conf)


def render_network(draw, font, font_sm, conf):
    """Page 2: Network interfaces."""
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=BG)

    y = draw_header(draw, font, font_sm, "Network", 1)

    mode = conf.get("MODE", "span").upper()
    draw.text((10, y), "Mode:", fill=DIM, font=font_sm)
    draw.text((50, y), mode, fill=ACCENT, font=font)
    y += 18

    interfaces = get_interface_info()

    for iface in interfaces:
        draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
        y += 5

        name = iface["name"]
        state = iface["state"]
        state_color = GREEN if state == "UP" else RED if state == "DOWN" else YELLOW

        # Interface name and state
        draw.text((10, y), name, fill=TEXT, font=font)
        draw.text((WIDTH - 10, y), state, fill=state_color, font=font_sm, anchor="ra")
        y += 15

        # IP
        ip_str = iface["ips"][0] if iface["ips"] else "No IP"
        draw.text((18, y), ip_str, fill=DIM, font=font_sm)

        # Speed
        if iface["speed"]:
            draw.text((WIDTH - 10, y), iface["speed"], fill=DIM, font=font_sm, anchor="ra")
        y += 13

        # MAC (abbreviated)
        mac = iface.get("mac", "")
        if mac:
            draw.text((18, y), mac, fill=DIVIDER, font=font_sm)
        y += 15

        if y > HEIGHT - 25:
            break

    draw_footer(draw, font_sm, conf)


def render_services(draw, font, font_sm, conf):
    """Page 3: Detailed service status."""
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=BG)

    y = draw_header(draw, font, font_sm, "Services", 2)

    services = [
        ("Capture", "networktap-capture"),
        ("Suricata", "networktap-suricata"),
        ("Zeek", "networktap-zeek"),
        ("Web UI", "networktap-web"),
        ("Display", "networktap-display"),
        ("Cleanup", "networktap-cleanup.timer"),
        ("Console", "networktap-console"),
    ]

    for label, svc_name in services:
        active, sub = check_service(svc_name)
        uptime = get_service_uptime(svc_name) if active else None

        dot_color = GREEN if active else RED
        cx, cy = 16, y + 6
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=dot_color)

        draw.text((26, y), label, fill=TEXT, font=font)

        # Sub-state
        sub_color = DIM if active else RED
        draw.text((130, y), sub, fill=sub_color, font=font_sm)

        # Uptime
        if uptime:
            draw.text((WIDTH - 10, y), uptime, fill=DIM, font=font_sm, anchor="ra")

        y += 20

        if y > HEIGHT - 25:
            break

    # Version at bottom
    y = HEIGHT - 32
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 4
    version = get_version()
    draw.text((10, y), f"NetworkTap v{version}", fill=DIM, font=font_sm)

    draw_footer(draw, font_sm, conf)


def render_alerts(draw, font, font_sm, conf):
    """Page 4: Alert summary."""
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=BG)

    y = draw_header(draw, font, font_sm, "Alerts", 3)

    eve_path = conf.get("SURICATA_EVE_LOG", "/var/log/suricata/eve.json")
    total_alerts = count_alerts(eve_path)
    top_sigs, severities = get_recent_alert_sigs(eve_path)

    # Total count
    draw.text((10, y), "Total Events", fill=DIM, font=font_sm)
    draw.text((WIDTH - 10, y), str(total_alerts), fill=TEXT, font=font, anchor="ra")
    y += 18

    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 5

    # Severity breakdown (from recent tail)
    draw.text((10, y), "Recent (last 200):", fill=DIM, font=font_sm)
    y += 15

    sev_labels = [(1, "High", RED), (2, "Medium", YELLOW), (3, "Low", DIM)]
    for sev, label, color in sev_labels:
        cnt = severities.get(sev, 0)
        draw.text((18, y), label, fill=color, font=font_sm)
        draw.text((90, y), str(cnt), fill=TEXT, font=font_sm)
        y += 14

    y += 2
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 5

    # Top signatures
    draw.text((10, y), "Top Signatures:", fill=DIM, font=font_sm)
    y += 15

    if not top_sigs:
        draw.text((18, y), "No alerts", fill=DIM, font=font_sm)
    else:
        for sig, cnt in top_sigs:
            # Truncate long signatures
            if len(sig) > 32:
                sig = sig[:30] + ".."
            draw.text((18, y), sig, fill=TEXT, font=font_sm)
            draw.text((WIDTH - 10, y), str(cnt), fill=ACCENT, font=font_sm, anchor="ra")
            y += 14
            if y > HEIGHT - 25:
                break

    draw_footer(draw, font_sm, conf)


def render_system(draw, font, font_sm, conf):
    """Page 5: System information."""
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=BG)

    y = draw_header(draw, font, font_sm, "System", 4)

    capture_dir = conf.get("CAPTURE_DIR", "/var/lib/networktap/captures")

    rows = [
        ("Host", socket.gethostname()),
        ("Uptime", get_uptime()),
        ("CPU Temp", get_cpu_temp()),
        ("Load Avg", get_load_average()),
        ("Kernel", get_kernel_version()),
    ]

    for label, value in rows:
        draw.text((10, y), label, fill=DIM, font=font_sm)
        draw.text((WIDTH - 10, y), str(value), fill=TEXT, font=font, anchor="ra")
        y += 17

    y += 2
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 6

    # Memory detail
    mem_pct, used_mb, total_mb = get_memory_info()
    draw.text((10, y), "Memory", fill=DIM, font=font_sm)
    draw.text((WIDTH - 10, y), f"{used_mb}MB / {total_mb}MB ({mem_pct}%)", fill=TEXT, font=font_sm, anchor="ra")
    y += 17

    # Disk detail
    disk_pct, used_gb, total_gb = get_disk_info(capture_dir)
    draw.text((10, y), "Disk", fill=DIM, font=font_sm)
    draw.text((WIDTH - 10, y), f"{used_gb:.1f}GB / {total_gb:.1f}GB ({disk_pct}%)", fill=TEXT, font=font_sm, anchor="ra")
    y += 17

    # PCAP storage
    pcap_count, pcap_size = count_pcaps(capture_dir)
    pcap_size_mb = pcap_size / (1024 * 1024)
    draw.text((10, y), "PCAPs", fill=DIM, font=font_sm)
    if pcap_size_mb > 1024:
        size_str = f"{pcap_count} files ({pcap_size_mb / 1024:.1f}GB)"
    else:
        size_str = f"{pcap_count} files ({pcap_size_mb:.0f}MB)"
    draw.text((WIDTH - 10, y), size_str, fill=TEXT, font=font_sm, anchor="ra")
    y += 17

    y += 2
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 6

    # Version + NIC config
    version = get_version()
    draw.text((10, y), "Version", fill=DIM, font=font_sm)
    draw.text((WIDTH - 10, y), f"v{version}", fill=ACCENT, font=font_sm, anchor="ra")
    y += 17

    nic1 = conf.get("NIC1", "eth0")
    nic2 = conf.get("NIC2", "eth1")
    draw.text((10, y), "NICs", fill=DIM, font=font_sm)
    draw.text((WIDTH - 10, y), f"{nic1} / {nic2}", fill=TEXT, font=font_sm, anchor="ra")

    draw_footer(draw, font_sm, conf)


# Page renderer list (matches PAGES order)
PAGE_RENDERERS = [render_dashboard, render_network, render_services, render_alerts, render_system]


# ─── Display & Touch Hardware ───────────────────────────────────────


def find_font(size):
    """Try to load a good monospace/sans font, fall back to default."""
    from PIL import ImageFont

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def set_backlight(on):
    """Control FR202 backlight via I2C expander at 0x3C on bus 1."""
    DEV_ADDR = 0x3C
    REG_OUTPUT = 0x01
    REG_CONFIG = 0x03
    PIN_DIRS = 0x81

    try:
        try:
            import smbus2 as smbus
        except ImportError:
            import smbus
        bus = smbus.SMBus(1)
        bus.write_byte_data(DEV_ADDR, REG_CONFIG, PIN_DIRS)
        current = bus.read_byte_data(DEV_ADDR, REG_OUTPUT)
        if on:
            bus.write_byte_data(DEV_ADDR, REG_OUTPUT, current & ~(1 << 6))
        else:
            bus.write_byte_data(DEV_ADDR, REG_OUTPUT, current | (1 << 6))
        bus.close()
    except Exception:
        try:
            if on:
                subprocess.run(["i2cset", "-y", "1", "0x3c", "0x03", "0x81"],
                               capture_output=True, timeout=5)
                subprocess.run(["i2cset", "-y", "1", "0x3c", "0x01", "0xbf"],
                               capture_output=True, timeout=5)
            else:
                subprocess.run(["i2cset", "-y", "1", "0x3c", "0x03", "0x81"],
                               capture_output=True, timeout=5)
                subprocess.run(["i2cset", "-y", "1", "0x3c", "0x01", "0xff"],
                               capture_output=True, timeout=5)
        except Exception as e:
            log.warning(f"Could not set backlight: {e}")


def init_display():
    """Initialize the ST7789 SPI display. Returns the display object."""
    import st7789

    rst_pin = None
    try:
        import gpiod
        from gpiod.line import Direction, Value, Drive
        import gpiodevice
        rst_cfg = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE,
            drive=Drive.OPEN_DRAIN,
            active_low=True,
        )
        rst_pin = gpiodevice.get_pin(27, "st7789-rst", rst_cfg)
        log.info("Reset pin configured: GPIO 27 (open-drain)")
    except Exception as e:
        log.warning(f"Could not configure GPIO 27 reset pin: {e}")

    disp = st7789.ST7789(
        height=HEIGHT,
        width=WIDTH,
        rotation=180,
        port=3,
        cs=0,
        dc=16,
        rst=rst_pin,
        backlight=None,
        spi_speed_hz=60_000_000,
    )

    disp._spi.mode = 3
    disp._init()

    set_backlight(True)
    log.info("ST7789 display initialized (320x240, SPI3, DC=16, RST=27, mode=3, rot=180)")
    return disp


def init_touch():
    """Initialize touch controller (ST1633i at 0x70 on I2C bus 5, interrupt GPIO 26).

    Returns (touch_line, smbus_module) or (None, None) if unavailable.
    """
    try:
        import gpiod
        from gpiod.line import Direction, Edge
        import gpiodevice

        touch_line, _ = gpiodevice.get_pin(
            26, "st7789-touch-int",
            gpiod.LineSettings(direction=Direction.INPUT, edge_detection=Edge.FALLING, active_low=True),
        )

        try:
            import smbus2 as smbus
        except ImportError:
            import smbus

        # Quick test read to verify touch controller is responsive
        i2c = smbus.SMBus(5)
        i2c.read_byte_data(0x70, ST1633_REG["status"])
        i2c.close()

        log.info("Touch controller initialized (ST1633i, bus 5, addr 0x70, int GPIO 26)")
        return touch_line, smbus
    except Exception as e:
        log.warning(f"Touch controller not available: {e}")
        return None, None


def read_touch(touch_line, smbus_mod):
    """Check for a touch event. Returns True if screen was tapped."""
    if touch_line is None:
        return False

    try:
        # Wait for edge event with short timeout (non-blocking-ish)
        if touch_line.wait_edge_events(0.05):
            touch_line.read_edge_events()
            # Read touch data to confirm it's a real touch
            try:
                i2c = smbus_mod.SMBus(5)
                t_hi = i2c.read_byte_data(0x70, ST1633_REG["xy0_hi"])
                i2c.close()
                # Bit 7 of xy0_hi indicates touch detected
                return bool(t_hi & 0x80)
            except IOError:
                return False
    except Exception:
        pass
    return False


# ─── Main Loop ──────────────────────────────────────────────────────


def main():
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        running = False
        log.info("Shutting down display...")

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        log.error("Pillow not installed. Install with: pip3 install pillow")
        sys.exit(1)

    # Init hardware display
    display = None
    try:
        display = init_display()
    except Exception as e:
        log.warning(f"Could not initialize ST7789 display: {e}")
        log.warning("Running in headless mode (logging frames to console)")

    # Init touch
    touch_line, smbus_mod = init_touch()

    # Load fonts
    font = find_font(14)
    font_sm = find_font(11)

    # Read display settings from config
    conf = load_config()
    refresh_interval = int(conf.get("DISPLAY_REFRESH", REFRESH_INTERVAL))
    backlight_timeout = int(conf.get("DISPLAY_BACKLIGHT_TIMEOUT", BACKLIGHT_TIMEOUT))
    default_page = conf.get("DISPLAY_DEFAULT_PAGE", DEFAULT_PAGE)

    # Clamp to sane ranges
    refresh_interval = max(1, min(60, refresh_interval))
    backlight_timeout = max(0, min(3600, backlight_timeout))

    # Set initial page from config
    page_idx = PAGES.index(default_page) if default_page in PAGES else 0
    idle_time = 0.0
    backlight_on = True
    last_render = 0
    debounce_time = 0.0
    config_reload_time = time.time()

    log.info("Starting display loop (%d pages, refresh=%ds, backlight_timeout=%ds, default=%s)",
             len(PAGES), refresh_interval, backlight_timeout, PAGES[page_idx])

    while running:
        now = time.time()
        needs_render = False

        # Reload config every 60s to pick up settings changes from the web UI
        if now - config_reload_time >= 60:
            conf = load_config()
            refresh_interval = max(1, min(60, int(conf.get("DISPLAY_REFRESH", REFRESH_INTERVAL))))
            backlight_timeout = max(0, min(3600, int(conf.get("DISPLAY_BACKLIGHT_TIMEOUT", BACKLIGHT_TIMEOUT))))
            config_reload_time = now

        # Check for touch input
        touched = read_touch(touch_line, smbus_mod)

        if touched and (now - debounce_time) > 0.5:
            debounce_time = now
            idle_time = 0.0

            if not backlight_on:
                # First tap wakes the screen without changing page
                set_backlight(True)
                backlight_on = True
                log.info("Backlight re-enabled (touch wake)")
            else:
                # Cycle to next page
                page_idx = (page_idx + 1) % len(PAGES)
                log.info("Switched to page: %s", PAGES[page_idx])

            needs_render = True

        # Auto-dim backlight after timeout (0 = never dim)
        if backlight_on and backlight_timeout > 0 and idle_time >= backlight_timeout:
            set_backlight(False)
            backlight_on = False
            log.info("Backlight dimmed (idle timeout)")

        # Periodic refresh
        if now - last_render >= refresh_interval:
            needs_render = True

        if needs_render:
            try:
                conf = load_config()
                img = Image.new("RGB", (WIDTH, HEIGHT), BG)
                draw = ImageDraw.Draw(img)

                PAGE_RENDERERS[page_idx](draw, font, font_sm, conf)

                if display is not None:
                    display.display(img)
                else:
                    log.info("Frame rendered: page=%s (no hardware display)", PAGES[page_idx])

                last_render = time.time()
            except Exception:
                log.exception("Error rendering frame")

        # Small sleep for touch polling responsiveness
        if not touched:
            time.sleep(0.1)
            idle_time += 0.1

    # Blank screen on exit
    if display is not None:
        try:
            from PIL import Image as PILImage
            blank = PILImage.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
            display.display(blank)
            set_backlight(False)
        except Exception:
            pass

    log.info("Display stopped")


if __name__ == "__main__":
    main()
