"""PCAP analysis and search functionality."""

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from core.config import get_config

logger = logging.getLogger("networktap.pcap")


@dataclass
class PcapMetadata:
    filename: str
    path: str
    size: int
    packets: int = 0
    duration: float = 0.0
    start_time: str = ""
    end_time: str = ""
    data_link: str = ""


@lru_cache(maxsize=1)
def get_capinfos_path() -> Optional[str]:
    """Find capinfos binary (from Wireshark/tshark)."""
    for path in ["/usr/bin/capinfos", "/usr/local/bin/capinfos"]:
        if Path(path).exists():
            return path
    return None


@lru_cache(maxsize=1)
def get_tshark_path() -> Optional[str]:
    """Find tshark binary."""
    for path in ["/usr/bin/tshark", "/usr/local/bin/tshark"]:
        if Path(path).exists():
            return path
    return None


@lru_cache(maxsize=1)
def get_tcpdump_path() -> Optional[str]:
    """Find tcpdump binary."""
    for path in ["/usr/sbin/tcpdump", "/usr/bin/tcpdump"]:
        if Path(path).exists():
            return path
    return None


async def get_pcap_metadata(pcap_path: Path) -> Optional[PcapMetadata]:
    """Get metadata about a pcap file using capinfos or tcpdump."""
    if not pcap_path.exists():
        return None
    
    metadata = PcapMetadata(
        filename=pcap_path.name,
        path=str(pcap_path),
        size=pcap_path.stat().st_size,
    )
    
    capinfos = get_capinfos_path()
    if capinfos:
        try:
            proc = await asyncio.create_subprocess_exec(
                capinfos, "-M", str(pcap_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            
            for line in stdout.decode().splitlines():
                if "Number of packets:" in line:
                    metadata.packets = int(line.split(":")[-1].strip())
                elif "Capture duration:" in line:
                    try:
                        metadata.duration = float(line.split(":")[-1].strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "First packet time:" in line:
                    metadata.start_time = line.split(":", 1)[-1].strip()
                elif "Last packet time:" in line:
                    metadata.end_time = line.split(":", 1)[-1].strip()
                elif "Data link type:" in line:
                    metadata.data_link = line.split(":")[-1].strip()
        except Exception as e:
            logger.warning("capinfos failed: %s", e)
    else:
        # Fallback to tcpdump -r for basic stats
        tcpdump = get_tcpdump_path()
        if tcpdump:
            try:
                proc = await asyncio.create_subprocess_exec(
                    tcpdump, "-r", str(pcap_path), "-c", "1", "-n",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                # tcpdump outputs stats to stderr
                for line in stderr.decode().splitlines():
                    if "packets" in line.lower():
                        match = re.search(r"(\d+) packets", line)
                        if match:
                            metadata.packets = int(match.group(1))
            except Exception as e:
                logger.warning("tcpdump stats failed: %s", e)
    
    return metadata


async def search_pcap(
    pcap_path: Path,
    filter_expr: Optional[str] = None,
    src_ip: Optional[str] = None,
    dest_ip: Optional[str] = None,
    port: Optional[int] = None,
    protocol: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Search a pcap file for matching packets."""
    if not pcap_path.exists():
        return []
    
    # Build BPF filter
    filters = []
    if filter_expr:
        filters.append(f"({filter_expr})")
    if src_ip:
        filters.append(f"src host {src_ip}")
    if dest_ip:
        filters.append(f"dst host {dest_ip}")
    if port:
        filters.append(f"port {port}")
    if protocol:
        filters.append(protocol.lower())
    
    bpf_filter = " and ".join(filters) if filters else ""
    
    # Prefer tshark for JSON output
    tshark = get_tshark_path()
    if tshark:
        return await _search_with_tshark(pcap_path, bpf_filter, limit)
    
    # Fallback to tcpdump
    tcpdump = get_tcpdump_path()
    if tcpdump:
        return await _search_with_tcpdump(pcap_path, bpf_filter, limit)
    
    return []


async def _search_with_tshark(pcap_path: Path, bpf_filter: str, limit: int) -> list[dict]:
    """Search pcap using tshark."""
    tshark = get_tshark_path()
    
    cmd = [
        tshark,
        "-r", str(pcap_path),
        "-c", str(limit),
        "-T", "json",
        "-e", "frame.number",
        "-e", "frame.time",
        "-e", "frame.len",
        "-e", "ip.src",
        "-e", "ip.dst",
        "-e", "ip.proto",
        "-e", "tcp.srcport",
        "-e", "tcp.dstport",
        "-e", "udp.srcport",
        "-e", "udp.dstport",
        "-e", "_ws.col.Protocol",
        "-e", "_ws.col.Info",
    ]
    
    if bpf_filter:
        cmd.extend(["-Y", bpf_filter])
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        
        packets = json.loads(stdout.decode()) if stdout else []
        
        results = []
        for pkt in packets:
            layers = pkt.get("_source", {}).get("layers", {})
            results.append({
                "frame": layers.get("frame.number", [""])[0],
                "time": layers.get("frame.time", [""])[0],
                "length": layers.get("frame.len", ["0"])[0],
                "src_ip": layers.get("ip.src", [""])[0],
                "dest_ip": layers.get("ip.dst", [""])[0],
                "src_port": layers.get("tcp.srcport", layers.get("udp.srcport", [""]))[0],
                "dest_port": layers.get("tcp.dstport", layers.get("udp.dstport", [""]))[0],
                "protocol": layers.get("_ws.col.Protocol", [""])[0],
                "info": layers.get("_ws.col.Info", [""])[0],
            })
        
        return results
    except Exception as e:
        logger.error("tshark search failed: %s", e)
        return []


async def _search_with_tcpdump(pcap_path: Path, bpf_filter: str, limit: int) -> list[dict]:
    """Search pcap using tcpdump."""
    tcpdump = get_tcpdump_path()
    
    cmd = [tcpdump, "-r", str(pcap_path), "-n", "-c", str(limit)]
    if bpf_filter:
        cmd.append(bpf_filter)
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        
        results = []
        for i, line in enumerate(stdout.decode().splitlines(), 1):
            # Parse tcpdump output (basic parsing)
            parts = line.split()
            if len(parts) < 4:
                continue
            
            results.append({
                "frame": str(i),
                "time": parts[0] if parts else "",
                "raw": line,
                "src_ip": "",
                "dest_ip": "",
                "protocol": "",
                "info": " ".join(parts[1:]) if len(parts) > 1 else "",
            })
        
        return results
    except Exception as e:
        logger.error("tcpdump search failed: %s", e)
        return []


async def get_pcap_connections(pcap_path: Path, limit: int = 100) -> list[dict]:
    """Get unique connections from a pcap file."""
    tshark = get_tshark_path()
    if not tshark or not pcap_path.exists():
        return []
    
    cmd = [
        tshark,
        "-r", str(pcap_path),
        "-q",
        "-z", "conv,ip",
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        
        connections = []
        lines = stdout.decode().splitlines()
        
        # Skip header lines
        data_started = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if "<->" in line:
                data_started = True
                parts = line.split()
                if len(parts) >= 8:
                    connections.append({
                        "src_ip": parts[0],
                        "dest_ip": parts[2],
                        "frames_out": parts[3],
                        "bytes_out": parts[4],
                        "frames_in": parts[5],
                        "bytes_in": parts[6],
                        "total_frames": parts[7] if len(parts) > 7 else "",
                        "total_bytes": parts[8] if len(parts) > 8 else "",
                    })
            
            if len(connections) >= limit:
                break
        
        return connections
    except Exception as e:
        logger.error("Connection extraction failed: %s", e)
        return []


async def get_pcap_protocols(pcap_path: Path) -> dict:
    """Get protocol distribution from a pcap file."""
    tshark = get_tshark_path()
    if not tshark or not pcap_path.exists():
        return {}

    cmd = [
        tshark,
        "-r", str(pcap_path),
        "-q",
        "-z", "io,phs",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)

        protocols = {}
        for line in stdout.decode().splitlines():
            line = line.strip()
            if not line or line.startswith("=") or "frames" in line.lower():
                continue

            # Parse protocol hierarchy stats
            match = re.match(r"(\S+)\s+frames:(\d+)\s+bytes:(\d+)", line)
            if match:
                proto = match.group(1)
                frames = int(match.group(2))
                protocols[proto] = frames

        return protocols
    except Exception as e:
        logger.error("Protocol stats failed: %s", e)
        return {}


async def count_filtered_packets(
    pcap_path: Path,
    bpf_filter: Optional[str] = None,
) -> int:
    """Count packets matching a BPF filter in a pcap file."""
    if not pcap_path.exists():
        return 0

    tcpdump = get_tcpdump_path()
    if not tcpdump:
        return 0

    cmd = [tcpdump, "-r", str(pcap_path), "-n"]
    if bpf_filter:
        cmd.append(bpf_filter)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        # Count lines of output
        count = len(stdout.decode().strip().splitlines())

        # Also check stderr for packet count summary
        for line in stderr.decode().splitlines():
            if "packets" in line.lower():
                match = re.search(r"(\d+)\s+packets?", line)
                if match:
                    count = int(match.group(1))
                    break

        return count
    except Exception as e:
        logger.error("Packet count failed: %s", e)
        return 0


async def extract_filtered_pcap(
    pcap_path: Path,
    output_path: Path,
    bpf_filter: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> bool:
    """Extract packets matching filter to a new pcap file."""
    if not pcap_path.exists():
        return False

    tcpdump = get_tcpdump_path()
    if not tcpdump:
        return False

    cmd = [tcpdump, "-r", str(pcap_path), "-w", str(output_path), "-n"]

    # Build filter expression
    filters = []
    if bpf_filter:
        filters.append(f"({bpf_filter})")

    if filters:
        cmd.append(" and ".join(filters))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        # Check if output file was created and has data
        if output_path.exists() and output_path.stat().st_size > 0:
            return True

        logger.warning("Filtered pcap extraction produced empty file: %s", stderr.decode())
        return False

    except Exception as e:
        logger.error("Filtered extraction failed: %s", e)
        return False


def build_bpf_filter(
    src_ip: Optional[str] = None,
    dst_ip: Optional[str] = None,
    src_port: Optional[int] = None,
    dst_port: Optional[int] = None,
    protocol: Optional[str] = None,
    raw_filter: Optional[str] = None,
) -> str:
    """Build a BPF filter string from individual components."""
    filters = []

    if raw_filter:
        return raw_filter.strip()

    if src_ip:
        filters.append(f"src host {src_ip}")
    if dst_ip:
        filters.append(f"dst host {dst_ip}")
    if src_port:
        filters.append(f"src port {src_port}")
    if dst_port:
        filters.append(f"dst port {dst_port}")
    if protocol:
        filters.append(protocol.lower())

    return " and ".join(filters)


# ══════════════════════════════════════════════════════════════════════════════
# PACKET VIEWER - Lightweight packet inspection
# ══════════════════════════════════════════════════════════════════════════════

async def get_packets(
    pcap_path: Path,
    offset: int = 0,
    limit: int = 50,
    display_filter: Optional[str] = None,
) -> dict:
    """
    Get paginated packet list from a PCAP file.
    Uses tshark for efficient on-demand parsing.
    """
    if not pcap_path.exists():
        return {"packets": [], "total": 0, "offset": offset, "limit": limit}

    tshark = get_tshark_path()
    if not tshark:
        return {"packets": [], "total": 0, "offset": offset, "limit": limit, "error": "tshark not found"}

    # First get total count
    total = await _get_packet_count(pcap_path, display_filter)

    # Build tshark command for packet list
    cmd = [
        tshark,
        "-r", str(pcap_path),
        "-T", "ek",  # Elasticsearch JSON format - one line per packet
        "-e", "frame.number",
        "-e", "frame.time_relative",
        "-e", "frame.len",
        "-e", "eth.src",
        "-e", "eth.dst",
        "-e", "ip.src",
        "-e", "ip.dst",
        "-e", "ipv6.src",
        "-e", "ipv6.dst",
        "-e", "tcp.srcport",
        "-e", "tcp.dstport",
        "-e", "tcp.flags",
        "-e", "tcp.stream",
        "-e", "udp.srcport",
        "-e", "udp.dstport",
        "-e", "udp.stream",
        "-e", "_ws.col.Protocol",
        "-e", "_ws.col.Info",
    ]

    if display_filter:
        cmd.extend(["-Y", display_filter])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        packets = []
        lines = stdout.decode().strip().split('\n')

        # Process only the requested range
        for i, line in enumerate(lines):
            if i < offset:
                continue
            if i >= offset + limit:
                break

            if not line.strip():
                continue

            try:
                data = json.loads(line)
                if "layers" not in data:
                    continue

                layers = data["layers"]

                # Extract fields (tshark returns arrays)
                def get_field(name):
                    val = layers.get(name, [])
                    return val[0] if val else ""

                src_ip = get_field("ip_src") or get_field("ipv6_src")
                dst_ip = get_field("ip_dst") or get_field("ipv6_dst")
                src_port = get_field("tcp_srcport") or get_field("udp_srcport")
                dst_port = get_field("tcp_dstport") or get_field("udp_dstport")
                stream_id = get_field("tcp_stream") or get_field("udp_stream")

                packets.append({
                    "number": int(get_field("frame_number") or 0),
                    "time": float(get_field("frame_time_relative") or 0),
                    "length": int(get_field("frame_len") or 0),
                    "src_mac": get_field("eth_src"),
                    "dst_mac": get_field("eth_dst"),
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "src_port": src_port,
                    "dst_port": dst_port,
                    "protocol": get_field("_ws_col_Protocol"),
                    "info": get_field("_ws_col_Info"),
                    "tcp_flags": get_field("tcp_flags"),
                    "stream_id": stream_id,
                })
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                continue

        return {
            "packets": packets,
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    except asyncio.TimeoutError:
        return {"packets": [], "total": 0, "offset": offset, "limit": limit, "error": "timeout"}
    except Exception as e:
        logger.error("get_packets failed: %s", e)
        return {"packets": [], "total": 0, "offset": offset, "limit": limit, "error": str(e)}


async def _get_packet_count(pcap_path: Path, display_filter: Optional[str] = None) -> int:
    """Get total packet count, optionally with display filter."""
    capinfos = get_capinfos_path()

    if not display_filter and capinfos:
        # Fast path: use capinfos for unfiltered count
        try:
            proc = await asyncio.create_subprocess_exec(
                capinfos, "-c", str(pcap_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            for line in stdout.decode().splitlines():
                if "Number of packets:" in line:
                    return int(line.split(":")[-1].strip())
        except Exception:
            pass

    # Slow path: count with tshark
    tshark = get_tshark_path()
    if not tshark:
        return 0

    cmd = [tshark, "-r", str(pcap_path), "-T", "fields", "-e", "frame.number"]
    if display_filter:
        cmd.extend(["-Y", display_filter])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        return len(stdout.decode().strip().split('\n'))
    except Exception:
        return 0


async def get_packet_detail(pcap_path: Path, frame_number: int) -> Optional[dict]:
    """
    Get detailed information about a specific packet including hex dump.
    """
    if not pcap_path.exists():
        return None

    tshark = get_tshark_path()
    if not tshark:
        return None

    # Get packet details as JSON
    cmd_json = [
        tshark,
        "-r", str(pcap_path),
        "-Y", f"frame.number == {frame_number}",
        "-T", "json",
        "-x",  # Include hex dump
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_json,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)

        packets = json.loads(stdout.decode()) if stdout else []
        if not packets:
            return None

        pkt = packets[0]
        source = pkt.get("_source", {})
        layers = source.get("layers", {})

        # Parse layer hierarchy
        layer_info = []
        for layer_name, layer_data in layers.items():
            if layer_name.startswith("_"):
                continue
            if isinstance(layer_data, dict):
                fields = []
                for key, val in layer_data.items():
                    if not key.startswith("_") and not key.endswith("_raw"):
                        fields.append({"name": key, "value": val})
                layer_info.append({
                    "name": layer_name,
                    "fields": fields[:50],  # Limit fields per layer
                })

        # Get hex dump
        hex_dump = ""
        for layer_name, layer_data in layers.items():
            if layer_name.endswith("_raw"):
                raw_data = layer_data
                if isinstance(raw_data, list):
                    raw_data = raw_data[0] if raw_data else ""
                if raw_data:
                    hex_dump = _format_hex_dump(raw_data)
                    break

        return {
            "frame_number": frame_number,
            "layers": layer_info,
            "hex_dump": hex_dump,
        }

    except Exception as e:
        logger.error("get_packet_detail failed: %s", e)
        return None


def _format_hex_dump(hex_string: str) -> str:
    """Format raw hex string into readable hex dump with ASCII."""
    result = []
    hex_string = hex_string.replace(":", "")

    for i in range(0, len(hex_string), 32):
        chunk = hex_string[i:i+32]
        offset = i // 2

        # Hex bytes with spaces
        hex_bytes = " ".join(chunk[j:j+2] for j in range(0, len(chunk), 2))
        hex_bytes = hex_bytes.ljust(48)

        # ASCII representation
        ascii_str = ""
        for j in range(0, len(chunk), 2):
            byte_val = int(chunk[j:j+2], 16)
            if 32 <= byte_val <= 126:
                ascii_str += chr(byte_val)
            else:
                ascii_str += "."

        result.append(f"{offset:08x}  {hex_bytes}  |{ascii_str}|")

    return "\n".join(result)


async def get_stream_data(
    pcap_path: Path,
    stream_type: str,  # "tcp" or "udp"
    stream_id: int,
    format: str = "ascii",  # "ascii", "hex", "raw"
) -> Optional[dict]:
    """
    Follow a TCP or UDP stream.
    """
    if not pcap_path.exists():
        return None

    tshark = get_tshark_path()
    if not tshark:
        return None

    if stream_type not in ("tcp", "udp"):
        return None

    cmd = [
        tshark,
        "-r", str(pcap_path),
        "-q",
        "-z", f"follow,{stream_type},{format},{stream_id}",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)

        output = stdout.decode()

        # Parse stream output
        lines = output.split('\n')
        content_lines = []
        in_content = False
        node0_addr = ""
        node1_addr = ""

        for line in lines:
            if line.startswith("==="):
                in_content = True
                continue
            if line.startswith("Follow:"):
                continue
            if "Node 0:" in line:
                node0_addr = line.split("Node 0:")[-1].strip()
                continue
            if "Node 1:" in line:
                node1_addr = line.split("Node 1:")[-1].strip()
                continue
            if in_content:
                content_lines.append(line)

        content = "\n".join(content_lines).strip()

        return {
            "stream_type": stream_type,
            "stream_id": stream_id,
            "format": format,
            "node0": node0_addr,
            "node1": node1_addr,
            "content": content,
            "length": len(content),
        }

    except Exception as e:
        logger.error("get_stream_data failed: %s", e)
        return None


async def get_stream_list(pcap_path: Path) -> list[dict]:
    """Get list of TCP/UDP streams in a PCAP."""
    if not pcap_path.exists():
        return []

    tshark = get_tshark_path()
    if not tshark:
        return []

    # Get TCP streams
    cmd = [
        tshark,
        "-r", str(pcap_path),
        "-q",
        "-z", "conv,tcp",
    ]

    streams = []

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)

        for line in stdout.decode().splitlines():
            if "<->" in line:
                parts = line.split()
                if len(parts) >= 6:
                    streams.append({
                        "type": "tcp",
                        "src": parts[0],
                        "dst": parts[2],
                        "frames": int(parts[3]) + int(parts[5]) if parts[3].isdigit() else 0,
                        "bytes": parts[4] + " / " + parts[6] if len(parts) > 6 else "",
                    })

        # Get UDP streams
        cmd[5] = "conv,udp"
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)

        for line in stdout.decode().splitlines():
            if "<->" in line:
                parts = line.split()
                if len(parts) >= 6:
                    streams.append({
                        "type": "udp",
                        "src": parts[0],
                        "dst": parts[2],
                        "frames": int(parts[3]) + int(parts[5]) if parts[3].isdigit() else 0,
                        "bytes": parts[4] + " / " + parts[6] if len(parts) > 6 else "",
                    })

    except Exception as e:
        logger.error("get_stream_list failed: %s", e)

    return streams[:100]  # Limit to 100 streams
