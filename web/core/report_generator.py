"""Report generation for alerts and statistics."""

import csv
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import get_config
from core.alert_parser import parse_suricata_alerts, parse_zeek_alerts
from core.stats_collector import get_traffic_stats
from core.system_monitor import get_system_stats

logger = logging.getLogger("networktap.reports")

REPORTS_DIR = Path("/var/lib/networktap/reports")


def generate_alerts_csv(hours: int = 24, limit: int = 10000) -> str:
    """Generate CSV report of alerts."""
    config = get_config()
    
    # Collect alerts
    suricata = parse_suricata_alerts(config.suricata_eve_log, limit=limit)
    zeek = parse_zeek_alerts(config.zeek_log_dir, limit=limit)
    
    all_alerts = suricata + zeek
    all_alerts.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Timestamp", "Source", "Severity", "Signature", "Category",
        "Src IP", "Src Port", "Dest IP", "Dest Port", "Protocol", "Action"
    ])
    
    # Data
    for alert in all_alerts:
        writer.writerow([
            alert.get("timestamp", ""),
            alert.get("source", ""),
            alert.get("severity", ""),
            alert.get("signature", ""),
            alert.get("category", ""),
            alert.get("src_ip", ""),
            alert.get("src_port", ""),
            alert.get("dest_ip", ""),
            alert.get("dest_port", ""),
            alert.get("proto", ""),
            alert.get("action", ""),
        ])
    
    return output.getvalue()


def generate_stats_csv(hours: int = 24) -> str:
    """Generate CSV report of traffic statistics."""
    stats = get_traffic_stats(hours)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Summary section
    writer.writerow(["NetworkTap Traffic Statistics Report"])
    writer.writerow(["Generated", datetime.now().isoformat()])
    writer.writerow(["Period", f"Last {hours} hours"])
    writer.writerow([])
    
    # Overview
    writer.writerow(["Summary"])
    writer.writerow(["Total Bytes", stats.total_bytes])
    writer.writerow(["Total Packets", stats.total_packets])
    writer.writerow(["Total Connections", stats.total_connections])
    writer.writerow(["Bytes In", stats.bytes_in])
    writer.writerow(["Bytes Out", stats.bytes_out])
    writer.writerow(["Unique Source IPs", stats.unique_src_ips])
    writer.writerow(["Unique Dest IPs", stats.unique_dest_ips])
    writer.writerow([])
    
    # Top Talkers
    writer.writerow(["Top Talkers"])
    writer.writerow(["IP", "Bytes"])
    for talker in stats.top_talkers:
        writer.writerow([talker["ip"], talker["bytes"]])
    writer.writerow([])
    
    # Top Ports
    writer.writerow(["Top Ports"])
    writer.writerow(["Port", "Service", "Count"])
    for port in stats.top_ports:
        writer.writerow([port["port"], port.get("service", ""), port["count"]])
    writer.writerow([])
    
    # Protocols
    writer.writerow(["Protocol Distribution"])
    writer.writerow(["Protocol", "Count"])
    for proto, count in stats.protocols.items():
        writer.writerow([proto, count])
    
    return output.getvalue()


def generate_system_report() -> dict:
    """Generate system status report as JSON."""
    config = get_config()
    stats = get_system_stats(config.capture_dir)
    traffic = get_traffic_stats(24)
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "hostname": config.mgmt_ip,
        "mode": config.mode,
        "system": stats,
        "traffic_24h": {
            "total_bytes": traffic.total_bytes,
            "total_connections": traffic.total_connections,
            "unique_ips": traffic.unique_src_ips + traffic.unique_dest_ips,
            "top_talkers": traffic.top_talkers[:5],
            "protocols": traffic.protocols,
        },
        "configuration": {
            "suricata_enabled": config.suricata_enabled,
            "zeek_enabled": config.zeek_enabled,
            "capture_interface": config.capture_interface,
            "retention_days": config.retention_days,
        },
    }
    
    return report


def generate_html_report(hours: int = 24) -> str:
    """Generate HTML report with alerts and stats."""
    config = get_config()
    
    # Collect data
    suricata = parse_suricata_alerts(config.suricata_eve_log, limit=100)
    zeek = parse_zeek_alerts(config.zeek_log_dir, limit=100)
    stats = get_traffic_stats(hours)
    system = get_system_stats(config.capture_dir)
    
    all_alerts = suricata + zeek
    all_alerts.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    
    # Severity counts
    severity_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for alert in all_alerts:
        sev = alert.get("severity", 3)
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>NetworkTap Report - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #0a0e17; color: #e2e8f0; }}
        h1 {{ color: #00d4aa; border-bottom: 2px solid #00d4aa; padding-bottom: 10px; }}
        h2 {{ color: #94a3b8; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #1a2234; border: 1px solid #2a3650; border-radius: 8px; padding: 20px; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #00d4aa; }}
        .stat-label {{ color: #64748b; font-size: 0.9em; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: #1a2234; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #2a3650; }}
        th {{ background: #111827; color: #64748b; text-transform: uppercase; font-size: 0.8em; }}
        tr:hover {{ background: #1f2b42; }}
        .severity-1 {{ color: #ef4444; }}
        .severity-2 {{ color: #f97316; }}
        .severity-3 {{ color: #eab308; }}
        .severity-4 {{ color: #3b82f6; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #2a3650; color: #64748b; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>NetworkTap Security Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Mode: {config.mode.upper()} | Period: Last {hours} hours</p>
    
    <h2>System Overview</h2>
    <div class="summary">
        <div class="stat-card">
            <div class="stat-value">{system.get('cpu_percent', 0):.1f}%</div>
            <div class="stat-label">CPU Usage</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{system.get('memory_percent', 0):.1f}%</div>
            <div class="stat-label">Memory Usage</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{system.get('disk_percent', 0):.1f}%</div>
            <div class="stat-label">Disk Usage</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{_format_uptime(system.get('uptime', 0))}</div>
            <div class="stat-label">Uptime</div>
        </div>
    </div>
    
    <h2>Traffic Statistics</h2>
    <div class="summary">
        <div class="stat-card">
            <div class="stat-value">{_format_bytes(stats.total_bytes)}</div>
            <div class="stat-label">Total Traffic</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats.total_connections:,}</div>
            <div class="stat-label">Connections</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats.unique_src_ips}</div>
            <div class="stat-label">Unique Sources</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats.unique_dest_ips}</div>
            <div class="stat-label">Unique Destinations</div>
        </div>
    </div>
    
    <h2>Alert Summary</h2>
    <div class="summary">
        <div class="stat-card">
            <div class="stat-value severity-1">{severity_counts.get(1, 0)}</div>
            <div class="stat-label">Critical (Sev 1)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value severity-2">{severity_counts.get(2, 0)}</div>
            <div class="stat-label">High (Sev 2)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value severity-3">{severity_counts.get(3, 0)}</div>
            <div class="stat-label">Medium (Sev 3)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value severity-4">{severity_counts.get(4, 0)}</div>
            <div class="stat-label">Low (Sev 4)</div>
        </div>
    </div>
    
    <h2>Top Talkers</h2>
    <table>
        <tr><th>IP Address</th><th>Bytes</th></tr>
        {"".join(f"<tr><td>{t['ip']}</td><td>{_format_bytes(t['bytes'])}</td></tr>" for t in stats.top_talkers[:10])}
    </table>
    
    <h2>Recent Alerts</h2>
    <table>
        <tr><th>Time</th><th>Severity</th><th>Source</th><th>Signature</th><th>Src IP</th><th>Dest IP</th></tr>
        {"".join(_format_alert_row(a) for a in all_alerts[:50])}
    </table>
    
    <div class="footer">
        <p>NetworkTap Network Monitoring Appliance | Report generated automatically</p>
    </div>
</body>
</html>"""
    
    return html


def _format_bytes(b: int) -> str:
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _format_uptime(seconds: int) -> str:
    """Format uptime to human readable."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    if days > 0:
        return f"{days}d {hours}h"
    return f"{hours}h"


def _format_alert_row(alert: dict) -> str:
    """Format an alert as HTML table row."""
    sev = alert.get("severity", 3)
    timestamp = alert.get("timestamp", "")[:19]  # Trim to seconds
    return f"""<tr>
        <td>{timestamp}</td>
        <td class="severity-{sev}">Sev {sev}</td>
        <td>{alert.get('source', '')}</td>
        <td>{alert.get('signature', '')[:60]}</td>
        <td>{alert.get('src_ip', '')}</td>
        <td>{alert.get('dest_ip', '')}</td>
    </tr>"""


def save_report(content: str, filename: str) -> Path:
    """Save report to file."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / filename
    with open(path, "w") as f:
        f.write(content)
    return path


def list_reports() -> list[dict]:
    """List saved reports."""
    if not REPORTS_DIR.exists():
        return []
    
    reports = []
    for f in sorted(REPORTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            reports.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    
    return reports
