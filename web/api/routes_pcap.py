"""PCAP file management API endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from core.auth import verify_credentials
from core.capture_manager import list_pcap_files, get_pcap_path
from core.config import get_config
from core.pcap_analyzer import (
    get_pcap_metadata,
    search_pcap,
    get_pcap_connections,
    get_pcap_protocols,
    count_filtered_packets,
    extract_filtered_pcap,
    build_bpf_filter,
    get_packets,
    get_packet_detail,
    get_stream_data,
    get_stream_list,
)
from pathlib import Path
from starlette.background import BackgroundTask
import uuid

router = APIRouter()


@router.get("/")
async def list_pcaps(user: Annotated[str, Depends(verify_credentials)]):
    """List all available pcap files."""
    config = get_config()
    files = list_pcap_files()

    total_size = sum(f["size"] for f in files)

    return {
        "files": files,
        "count": len(files),
        "total_size": total_size,
        "capture_dir": config.capture_dir,
    }


@router.get("/{filename:path}/download")
async def download_pcap(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Download a specific pcap file."""
    path = get_pcap_path(filename)

    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    media_type = "application/gzip" if path.suffix == ".gz" else "application/vnd.tcpdump.pcap"

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type=media_type,
    )


@router.get("/{filename:path}/info")
async def get_pcap_info(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Get metadata about a pcap file."""
    path = get_pcap_path(filename)
    
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    metadata = await get_pcap_metadata(path)
    
    if metadata is None:
        raise HTTPException(status_code=500, detail="Failed to read pcap metadata")
    
    return {
        "filename": metadata.filename,
        "size": metadata.size,
        "packets": metadata.packets,
        "duration": metadata.duration,
        "start_time": metadata.start_time,
        "end_time": metadata.end_time,
        "data_link": metadata.data_link,
    }


@router.get("/{filename:path}/search")
async def search_pcap_file(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
    filter: Optional[str] = Query(None, description="BPF filter expression"),
    src_ip: Optional[str] = Query(None),
    dest_ip: Optional[str] = Query(None),
    port: Optional[int] = Query(None),
    protocol: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """Search packets in a pcap file."""
    path = get_pcap_path(filename)
    
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    results = await search_pcap(
        path,
        filter_expr=filter,
        src_ip=src_ip,
        dest_ip=dest_ip,
        port=port,
        protocol=protocol,
        limit=limit,
    )
    
    return {"packets": results, "count": len(results)}


@router.get("/{filename:path}/connections")
async def get_pcap_conns(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
    limit: int = Query(100, ge=1, le=1000),
):
    """Get unique connections from a pcap file."""
    path = get_pcap_path(filename)
    
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    connections = await get_pcap_connections(path, limit)
    
    return {"connections": connections, "count": len(connections)}


@router.get("/{filename:path}/protocols")
async def get_pcap_proto_stats(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Get protocol distribution from a pcap file."""
    path = get_pcap_path(filename)

    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    protocols = await get_pcap_protocols(path)

    return {"protocols": protocols}


@router.get("/{filename:path}/count")
async def count_filtered(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
    src_ip: Optional[str] = Query(None),
    dst_ip: Optional[str] = Query(None),
    src_port: Optional[int] = Query(None),
    dst_port: Optional[int] = Query(None),
    protocol: Optional[str] = Query(None),
    filter: Optional[str] = Query(None, description="Raw BPF filter expression"),
):
    """Count packets matching the given filter."""
    path = get_pcap_path(filename)

    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    bpf = build_bpf_filter(
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=protocol,
        raw_filter=filter,
    )

    count = await count_filtered_packets(path, bpf)

    return {
        "filename": filename,
        "filter": bpf or "(none)",
        "matching_packets": count,
    }


@router.get("/{filename:path}/filter")
async def download_filtered(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
    src_ip: Optional[str] = Query(None),
    dst_ip: Optional[str] = Query(None),
    src_port: Optional[int] = Query(None),
    dst_port: Optional[int] = Query(None),
    protocol: Optional[str] = Query(None),
    filter: Optional[str] = Query(None, description="Raw BPF filter expression"),
):
    """Download a filtered subset of the pcap file."""
    path = get_pcap_path(filename)

    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    bpf = build_bpf_filter(
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=protocol,
        raw_filter=filter,
    )

    if not bpf:
        # No filter, just return the original file
        media_type = "application/gzip" if path.suffix == ".gz" else "application/vnd.tcpdump.pcap"
        return FileResponse(
            path=str(path),
            filename=path.name,
            media_type=media_type,
        )

    # Create filtered pcap in temp directory
    config = get_config()
    temp_dir = Path(config.capture_dir) / ".temp"
    temp_dir.mkdir(exist_ok=True)

    output_name = f"filtered_{uuid.uuid4().hex[:8]}_{path.stem}.pcap"
    output_path = temp_dir / output_name

    try:
        success = await extract_filtered_pcap(path, output_path, bpf)

        if not success or not output_path.exists():
            raise HTTPException(status_code=500, detail="Failed to create filtered pcap")

        return FileResponse(
            path=str(output_path),
            filename=output_name,
            media_type="application/vnd.tcpdump.pcap",
            background=BackgroundTask(lambda: output_path.unlink(missing_ok=True)),
        )
    except HTTPException:
        output_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# PACKET VIEWER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{filename:path}/packets")
async def list_packets(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    filter: Optional[str] = Query(None, description="Display filter expression"),
):
    """
    Get paginated packet list from a PCAP file.
    Returns packet headers without full decode for efficiency.
    """
    path = get_pcap_path(filename)

    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    result = await get_packets(path, offset=offset, limit=limit, display_filter=filter)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/{filename:path}/packets/{frame_number}")
async def packet_detail(
    filename: str,
    frame_number: int,
    user: Annotated[str, Depends(verify_credentials)],
):
    """
    Get detailed packet information including layer decode and hex dump.
    """
    path = get_pcap_path(filename)

    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    detail = await get_packet_detail(path, frame_number)

    if detail is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    return detail


@router.get("/{filename:path}/streams")
async def list_streams(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
):
    """
    List TCP and UDP streams in a PCAP file.
    """
    path = get_pcap_path(filename)

    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    streams = await get_stream_list(path)

    return {"streams": streams, "count": len(streams)}


@router.get("/{filename:path}/streams/{stream_type}/{stream_id}")
async def stream_content(
    filename: str,
    stream_type: str,
    stream_id: int,
    user: Annotated[str, Depends(verify_credentials)],
    format: str = Query("ascii", pattern="^(ascii|hex|raw)$"),
):
    """
    Follow a TCP or UDP stream and return its content.
    """
    path = get_pcap_path(filename)

    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    if stream_type not in ("tcp", "udp"):
        raise HTTPException(status_code=400, detail="stream_type must be 'tcp' or 'udp'")

    data = await get_stream_data(path, stream_type, stream_id, format)

    if data is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    return data
