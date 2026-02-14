"""WiFi Analysis Module - IDS & Client Tracking"""
import json
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import asyncio


@dataclass
class WirelessClient:
    """Tracked wireless client."""
    mac: str
    vendor: str
    first_seen: str
    last_seen: str
    probe_ssids: List[str]
    connected_to: Optional[str] = None
    signal_strength: int = 0
    packet_count: int = 0


@dataclass
class RogueAP:
    """Detected rogue access point."""
    bssid: str
    ssid: str
    channel: int
    first_seen: str
    reason: str  # "spoofed_ssid", "unexpected_ap", "evil_twin"
    severity: str  # "high", "medium", "low"
    signal: int = 0


@dataclass
class WirelessAlert:
    """Wireless IDS alert."""
    timestamp: str
    alert_type: str  # "deauth_attack", "rogue_ap", "channel_hop", "unusual_client"
    severity: str
    source_mac: str
    details: str
    

class WiFiAnalyzer:
    """Analyzes WiFi captures for IDS and client tracking."""
    
    def __init__(self, config_file: str = "/etc/networktap.conf"):
        self.config_file = config_file
        self.capture_dir = Path("/var/lib/networktap/wifi-captures")
        self.data_dir = Path("/var/lib/networktap/wifi-analysis")
        
        # Create directories if running as root, otherwise use temp dir
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            import tempfile
            self.data_dir = Path(tempfile.gettempdir()) / "networktap-wifi-analysis"
            self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.clients_file = self.data_dir / "clients.json"
        self.rogueaps_file = self.data_dir / "rogue_aps.json"
        self.alerts_file = self.data_dir / "alerts.json"
        
        self.known_ssids = set()
        self.load_config()
    
    def load_config(self):
        """Load known SSIDs from config."""
        try:
            if Path(self.config_file).exists():
                with open(self.config_file) as f:
                    for line in f:
                        if line.startswith("WIFI_KNOWN_SSIDS="):
                            ssids = line.split("=", 1)[1].strip().strip('"')
                            self.known_ssids = set(s.strip() for s in ssids.split(",") if s.strip())
        except Exception:
            pass
    
    async def analyze_latest_capture(self) -> Dict:
        """Analyze the most recent WiFi capture file."""
        if not self.capture_dir.exists():
            return {"error": "No capture directory"}
        
        # Find latest pcap
        pcaps = list(self.capture_dir.glob("wifi-*.pcap"))
        if not pcaps:
            return {"error": "No capture files found"}
        
        latest_pcap = max(pcaps, key=lambda p: p.stat().st_mtime)
        
        # Analyze with tshark (if available)
        try:
            result = await self._analyze_with_tshark(latest_pcap)
            return result
        except Exception as e:
            return {"error": f"Analysis failed: {e}"}
    
    async def _analyze_with_tshark(self, pcap_file: Path) -> Dict:
        """Analyze pcap with tshark."""
        stats = {
            "clients_found": 0,
            "aps_found": 0,
            "deauth_count": 0,
            "probe_requests": 0,
        }
        
        # Check if tshark is available
        proc = await asyncio.create_subprocess_exec(
            "which", "tshark",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        
        if proc.returncode != 0:
            return {"error": "tshark not installed", "stats": stats}
        
        # Count frames
        proc = await asyncio.create_subprocess_exec(
            "tshark", "-r", str(pcap_file), "-q", "-z", "io,stat,0",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            )
        stdout, _ = await proc.communicate()
        
        # Extract basic stats from output
        output = stdout.decode(errors="ignore")
        for line in output.splitlines():
            if "Frames" in line and "|" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    try:
                        stats["total_frames"] = int(parts[1].strip())
                    except:
                        pass
        
        return {"stats": stats, "pcap": str(pcap_file)}
    
    def get_clients(self) -> List[WirelessClient]:
        """Get tracked clients."""
        if not self.clients_file.exists():
            return []
        
        try:
            data = json.loads(self.clients_file.read_text())
            return [WirelessClient(**c) for c in data]
        except:
            return []
    
    def get_rogue_aps(self) -> List[RogueAP]:
        """Get detected rogue APs."""
        if not self.rogueaps_file.exists():
            return []
        
        try:
            data = json.loads(self.rogueaps_file.read_text())
            return [RogueAP(**ap) for ap in data]
        except:
            return []
    
    def get_alerts(self, since_minutes: int = 60) -> List[WirelessAlert]:
        """Get recent alerts."""
        if not self.alerts_file.exists():
            return []
        
        try:
            data = json.loads(self.alerts_file.read_text())
            cutoff = datetime.now() - timedelta(minutes=since_minutes)
            
            alerts = []
            for alert_data in data:
                alert = WirelessAlert(**alert_data)
                alert_time = datetime.fromisoformat(alert.timestamp)
                if alert_time >= cutoff:
                    alerts.append(alert)
            
            return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
        except:
            return []
    
    def detect_rogue_aps_from_survey(self, survey_data: List[Dict]) -> List[RogueAP]:
        """Detect rogue APs from site survey data."""
        rogues = []
        
        for ap in survey_data:
            ssid = ap.get("ssid", "")
            bssid = ap.get("bssid", "")
            channel = ap.get("channel", 0)
            signal = ap.get("signal", 0)
            
            # Check for unexpected APs
            if ssid and ssid not in self.known_ssids and self.known_ssids:
                rogues.append(RogueAP(
                    bssid=bssid,
                    ssid=ssid,
                    channel=channel,
                    first_seen=datetime.now().isoformat(),
                    reason="unexpected_ap",
                    severity="medium",
                    signal=signal,
                ))
            
            # Check for hidden SSIDs (potential evil twin)
            if not ssid or ssid == "<hidden>":
                rogues.append(RogueAP(
                    bssid=bssid,
                    ssid="<hidden>",
                    channel=channel,
                    first_seen=datetime.now().isoformat(),
                    reason="hidden_ssid",
                    severity="low",
                    signal=signal,
                ))
        
        # Save detected rogues
        if rogues:
            existing = self.get_rogue_aps()
            existing_bssids = {ap.bssid for ap in existing}
            
            new_rogues = [r for r in rogues if r.bssid not in existing_bssids]
            if new_rogues:
                all_rogues = existing + new_rogues
                self.rogueaps_file.write_text(
                    json.dumps([asdict(ap) for ap in all_rogues], indent=2)
                )
        
        return rogues
    
    def add_alert(self, alert: WirelessAlert):
        """Add a new wireless alert."""
        alerts = self.get_alerts(since_minutes=10080)  # Keep 1 week
        alerts.append(alert)
        
        # Save alerts
        self.alerts_file.write_text(
            json.dumps([asdict(a) for a in alerts], indent=2)
        )
    
    def get_client_stats(self) -> Dict:
        """Get client tracking statistics."""
        clients = self.get_clients()
        
        # Count unique clients
        unique_macs = len(set(c.mac for c in clients))
        
        # Count active clients (seen in last hour)
        cutoff = datetime.now() - timedelta(hours=1)
        active = sum(
            1 for c in clients 
            if datetime.fromisoformat(c.last_seen) >= cutoff
        )
        
        # Top probe SSIDs
        all_ssids = []
        for c in clients:
            all_ssids.extend(c.probe_ssids)
        
        ssid_counts = {}
        for ssid in all_ssids:
            ssid_counts[ssid] = ssid_counts.get(ssid, 0) + 1
        
        top_ssids = sorted(ssid_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_clients": unique_macs,
            "active_clients": active,
            "top_probe_ssids": [{"ssid": s, "count": c} for s, c in top_ssids],
        }
    
    def lookup_vendor(self, mac: str) -> str:
        """Lookup vendor from MAC OUI (simplified)."""
        # In production, would use OUI database
        oui = mac.upper().replace(":", "")[:6]
        
        # Simple vendor mapping (expand this in production)
        vendors = {
            "001122": "Cisco",
            "001B63": "Apple",
            "F0DEF1": "Apple",
            "ACDE48": "Apple",
            "001D09": "Intel",
            "00166C": "HP",
        }
        
        return vendors.get(oui, "Unknown")


# Global analyzer instance
_analyzer = None

def get_analyzer() -> WiFiAnalyzer:
    """Get or create global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = WiFiAnalyzer()
    return _analyzer
