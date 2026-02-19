#!/usr/bin/env python3
"""NetworkTap Front Panel Display - FR202 ST7789 2.4" 320x240 TFT

Renders system status to the OnLogic FR202 front panel display.
Uses PIL/Pillow for rendering and st7789 SPI driver for output.

Refreshes every 5 seconds with:
  - Mode, hostname, IP
  - CPU / Memory / Disk usage bars
  - Service status (capture, suricata, zeek, web)
  - Alert + PCAP counts
"""

import os
import sys
import time
import signal
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("display")

# Display dimensions
WIDTH = 320
HEIGHT = 240
REFRESH_INTERVAL = 5  # seconds

# Colors (RGB tuples)
BG = (13, 17, 23)
TEXT = (230, 237, 243)
DIM = (125, 133, 144)
ACCENT = (0, 212, 170)  # #00d4aa
GREEN = (63, 185, 80)
RED = (248, 81, 73)
YELLOW = (210, 153, 34)
BAR_BG = (33, 38, 45)
DIVIDER = (48, 54, 61)

# Config path
CONF_PATH = "/etc/networktap.conf"
CONF_FALLBACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "networktap.conf")


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
    """Check if a systemd service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", name],
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_cpu_percent():
    """Read CPU usage from /proc/stat (avoids psutil dependency)."""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        idle = int(parts[4])
        total = sum(int(x) for x in parts[1:])
        # Store for delta calculation
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


def get_memory_percent():
    """Read memory usage from /proc/meminfo."""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 1)
        avail = info.get("MemAvailable", total)
        return int(100 * (1 - avail / total))
    except Exception:
        return 0


def get_disk_percent(path="/var/lib/networktap/captures"):
    """Get disk usage percentage."""
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        if total == 0:
            return 0
        return int(100 * (1 - free / total))
    except Exception:
        return 0


def count_pcaps(capture_dir="/var/lib/networktap/captures"):
    """Count .pcap files in capture directory."""
    count = 0
    try:
        for f in os.listdir(capture_dir):
            if ".pcap" in f:
                count += 1
    except Exception:
        pass
    return count


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


def render_frame(draw, font, font_sm, conf):
    """Render one status frame onto the PIL ImageDraw."""
    mode = conf.get("MODE", "span").upper()
    ip = get_management_ip(conf) or "No IP"
    cpu = get_cpu_percent()
    mem = get_memory_percent()
    capture_dir = conf.get("CAPTURE_DIR", "/var/lib/networktap/captures")
    disk = get_disk_percent(capture_dir)
    eve_path = conf.get("SURICATA_EVE_LOG", "/var/log/suricata/eve.json")

    svc_capture = check_service("networktap-capture")
    svc_suricata = check_service("networktap-suricata")
    svc_zeek = check_service("networktap-zeek")
    svc_web = check_service("networktap-web")

    pcaps = count_pcaps(capture_dir)
    alerts = count_alerts(eve_path)

    # Background
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=BG)

    y = 6

    # ── Header ──
    draw.text((10, y), "NetworkTap", fill=ACCENT, font=font)
    draw.text((WIDTH - 10, y), mode, fill=TEXT, font=font, anchor="ra")
    y += 20

    # Divider
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 6

    # ── IP Address ──
    draw.text((10, y), "IP", fill=DIM, font=font_sm)
    draw.text((WIDTH - 10, y), ip, fill=TEXT, font=font, anchor="ra")
    y += 20

    # Divider
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 8

    # ── Resource bars ──
    bar_x = 60
    bar_w = WIDTH - bar_x - 42
    bar_h = 14

    for label, pct, color in [("CPU", cpu, ACCENT), ("MEM", mem, ACCENT), ("DISK", disk, YELLOW if disk > 80 else ACCENT)]:
        draw.text((10, y), label, fill=DIM, font=font_sm)
        # Bar background
        draw.rectangle([bar_x, y + 1, bar_x + bar_w, y + bar_h], fill=BAR_BG)
        # Bar fill
        fill_w = max(1, int(bar_w * pct / 100))
        if pct > 0:
            draw.rectangle([bar_x, y + 1, bar_x + fill_w, y + bar_h], fill=color)
        # Percentage text
        draw.text((WIDTH - 10, y + 1), f"{pct}%", fill=TEXT, font=font_sm, anchor="ra")
        y += bar_h + 6

    y += 2

    # Divider
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 8

    # ── Services ──
    draw.text((10, y), "SERVICES", fill=DIM, font=font_sm)
    y += 16

    services = [
        ("Capture", svc_capture),
        ("Suricata", svc_suricata),
        ("Zeek", svc_zeek),
        ("Web UI", svc_web),
    ]

    for i, (name, active) in enumerate(services):
        col = 10 if i % 2 == 0 else WIDTH // 2 + 5
        row_y = y + (i // 2) * 20

        dot_color = GREEN if active else RED
        # Draw status dot
        cx, cy = col + 5, row_y + 7
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=dot_color)
        # Label
        draw.text((col + 14, row_y), name, fill=TEXT, font=font_sm)

    y += 42

    # Divider
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 8

    # ── Stats row ──
    draw.text((10, y), "Alerts", fill=DIM, font=font_sm)
    draw.text((60, y), str(alerts), fill=TEXT, font=font)

    draw.text((WIDTH // 2 + 5, y), "PCAPs", fill=DIM, font=font_sm)
    draw.text((WIDTH // 2 + 55, y), str(pcaps), fill=TEXT, font=font)
    y += 20

    # ── Footer with time ──
    draw.line([(8, y), (WIDTH - 8, y)], fill=DIVIDER, width=1)
    y += 4
    now = time.strftime("%H:%M:%S")
    port = conf.get("WEB_PORT", "8443")
    draw.text((10, y + 2), f":{port}", fill=DIM, font=font_sm)
    draw.text((WIDTH - 10, y + 2), now, fill=DIM, font=font_sm, anchor="ra")


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


def init_display():
    """Initialize the ST7789 SPI display. Returns the display object.

    The FR202 uses SPI3 with cs0_pin=24 (dtoverlay=spi3-1cs,cs0_pin=24).
    SPI3 maps to /dev/spidev3.0 → port=3, cs=0.
    Backlight is controlled via I2C (fr202-i2c), not a GPIO pin.
    """
    import st7789

    # FR202: SPI3, CS0, DC on GPIO25, no GPIO backlight (I2C-controlled)
    disp = st7789.ST7789(
        height=HEIGHT,
        width=WIDTH,
        rotation=0,
        port=3,
        cs=0,
        dc=25,
        backlight=None,
        spi_speed_hz=60_000_000,
    )
    disp.begin()
    return disp


def main():
    # Graceful shutdown
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        running = False
        log.info("Shutting down display...")

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Import PIL
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        log.error("Pillow not installed. Install with: pip3 install pillow")
        sys.exit(1)

    # Try to init hardware display
    display = None
    try:
        display = init_display()
        log.info("ST7789 display initialized (320x240)")
    except Exception as e:
        log.warning(f"Could not initialize ST7789 display: {e}")
        log.warning("Running in headless mode (logging frames to console)")

    # Load fonts
    font = find_font(14)
    font_sm = find_font(11)

    log.info("Starting display loop (refresh every %ds)", REFRESH_INTERVAL)

    while running:
        try:
            conf = load_config()
            img = Image.new("RGB", (WIDTH, HEIGHT), BG)
            draw = ImageDraw.Draw(img)
            render_frame(draw, font, font_sm, conf)

            if display is not None:
                display.display(img)
            else:
                log.info("Frame rendered (no hardware display)")

        except Exception:
            log.exception("Error rendering frame")

        # Interruptible sleep
        for _ in range(REFRESH_INTERVAL * 10):
            if not running:
                break
            time.sleep(0.1)

    # Blank screen on exit
    if display is not None:
        try:
            from PIL import Image as PILImage
            blank = PILImage.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
            display.display(blank)
        except Exception:
            pass

    log.info("Display stopped")


if __name__ == "__main__":
    main()
