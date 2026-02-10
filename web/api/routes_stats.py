"""Statistics API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.auth import verify_credentials
from core.stats_collector import (
    get_traffic_stats,
    get_connection_summary,
    get_bandwidth_history,
)
from core.stats_history import get_stats_history
from core.zeek_parser import (
    get_dns_stats,
    get_connection_trends,
    get_service_distribution,
)

router = APIRouter()


@router.get("/traffic")
async def traffic_stats(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
):
    """Get traffic statistics for the specified time period."""
    stats = get_traffic_stats(hours)
    return stats.to_dict()


@router.get("/connections")
async def connection_list(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(1, ge=1, le=24),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get recent connections."""
    connections = get_connection_summary(hours, limit)
    return {"connections": connections, "count": len(connections)}


@router.get("/bandwidth")
async def bandwidth_data(
    user: Annotated[str, Depends(verify_credentials)],
    minutes: int = Query(60, ge=5, le=1440),
):
    """Get bandwidth history data for charting."""
    data = get_bandwidth_history(minutes)
    return {"data": data, "period_minutes": minutes}


@router.get("/summary")
async def stats_summary(user: Annotated[str, Depends(verify_credentials)]):
    """Get summary statistics for dashboard."""
    # 1 hour stats for quick summary
    stats = get_traffic_stats(1)
    
    return {
        "bytes_total": stats.total_bytes,
        "connections": stats.total_connections,
        "unique_ips": stats.unique_src_ips + stats.unique_dest_ips,
        "protocols": stats.protocols,
    }


@router.get("/history")
async def stats_history(
    user: Annotated[str, Depends(verify_credentials)],
    range: str = Query("1h", pattern="^(30m|1h|6h|1d|1w|1M)$"),
):
    """
    Get historical system and network stats for charting.

    Ranges: 30m, 1h, 6h, 1d, 1w, 1M
    """
    return get_stats_history(range)


@router.get("/dns")
async def dns_stats(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
):
    """Get DNS statistics including top domains and query types."""
    return get_dns_stats(hours)


@router.get("/trends")
async def connection_trends_endpoint(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
    interval: int = Query(15, ge=5, le=60),
):
    """Get connection count trends over time."""
    trends = get_connection_trends(hours, interval)
    return {"trends": trends, "hours": hours, "interval_minutes": interval}


@router.get("/services")
async def service_distribution_endpoint(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
):
    """Get service distribution from connection logs."""
    services = get_service_distribution(hours)
    return {"services": services, "hours": hours}
