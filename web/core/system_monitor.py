"""System resource monitoring using psutil."""

import time
from dataclasses import dataclass
from pathlib import Path

import psutil

# Prime the CPU percent counter so the first non-blocking call returns a real value
psutil.cpu_percent(interval=None)


@dataclass
class SystemStats:
    cpu_percent: float
    cpu_count: int
    memory_total: int
    memory_used: int
    memory_percent: float
    disk_total: int
    disk_used: int
    disk_free: int
    disk_percent: float
    uptime: int
    load_avg: list[float]
    boot_time: float


@dataclass
class InterfaceStats:
    name: str
    state: str
    mac: str
    mtu: int
    speed: int
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int
    drops_in: int
    drops_out: int
    addresses: list[str]


def get_system_stats(capture_dir: str = "/var/lib/networktap/captures") -> dict:
    """Gather current system statistics."""
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(capture_dir)
    except FileNotFoundError:
        disk = psutil.disk_usage("/")

    try:
        load = list(psutil.getloadavg())
    except (AttributeError, OSError):
        load = [0.0, 0.0, 0.0]

    return {
        "cpu_percent": cpu,
        "cpu_count": psutil.cpu_count(),
        "memory_total": mem.total,
        "memory_used": mem.used,
        "memory_percent": mem.percent,
        "disk_total": disk.total,
        "disk_used": disk.used,
        "disk_free": disk.free,
        "disk_percent": disk.percent,
        "uptime": int(time.time() - psutil.boot_time()),
        "load_avg": load,
        "boot_time": psutil.boot_time(),
    }


def get_interface_stats() -> list[dict]:
    """Get statistics for all network interfaces."""
    stats = psutil.net_io_counters(pernic=True)
    addrs = psutil.net_if_addrs()
    if_stats = psutil.net_if_stats()

    interfaces = []
    for name, counters in stats.items():
        if name == "lo":
            continue

        info = if_stats.get(name)
        addr_list = addrs.get(name, [])

        ip_addrs = []
        mac = ""
        for a in addr_list:
            if a.family.name == "AF_INET":
                ip_addrs.append(a.address)
            elif a.family.name == "AF_INET6" and not a.address.startswith("fe80"):
                ip_addrs.append(a.address)
            elif a.family.name in ("AF_LINK", "AF_PACKET"):
                mac = a.address

        interfaces.append({
            "name": name,
            "state": "up" if (info and info.isup) else "down",
            "mac": mac,
            "mtu": info.mtu if info else 0,
            "speed": info.speed if info else 0,
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
            "errors_in": counters.errin,
            "errors_out": counters.errout,
            "drops_in": counters.dropin,
            "drops_out": counters.dropout,
            "addresses": ip_addrs,
        })

    return interfaces


def get_service_status(service_name: str) -> dict:
    """Check if a systemd service is running."""
    import subprocess

    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True, text=True, timeout=5,
        )
        active = result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        active = "unknown"

    try:
        result = subprocess.run(
            ["systemctl", "is-enabled", service_name],
            capture_output=True, text=True, timeout=5,
        )
        enabled = result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        enabled = "unknown"

    return {
        "name": service_name,
        "active": active,
        "enabled": enabled,
        "running": active == "active",
    }


def get_all_services() -> list[dict]:
    """Get status of all NetworkTap services."""
    services = [
        "networktap-web",
        "networktap-capture",
        "networktap-suricata",
        "networktap-zeek",
        "networktap-cleanup.timer",
    ]
    return [get_service_status(s) for s in services]
