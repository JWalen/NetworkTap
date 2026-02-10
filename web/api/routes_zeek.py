"""Zeek log browsing API endpoints."""

from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.auth import verify_credentials
from core.zeek_parser import (
    get_available_logs,
    get_log_entries,
    get_log_entry_by_uid,
    search_logs,
    get_dns_stats,
    get_connection_trends,
    get_service_distribution,
)

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    log_types: Optional[list[str]] = None
    hours: int = 24
    limit: int = 100


@router.get("/logs")
async def list_log_types(user: Annotated[str, Depends(verify_credentials)]):
    """List available Zeek log types with estimated counts."""
    logs = get_available_logs()
    return {"logs": logs}


@router.get("/logs/{log_type}")
async def get_logs(
    log_type: str,
    user: Annotated[str, Depends(verify_credentials)],
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    ip: Optional[str] = Query(None, description="Filter by source or destination IP"),
    port: Optional[int] = Query(None, description="Filter by port"),
    proto: Optional[str] = Query(None, description="Filter by protocol (tcp/udp/icmp)"),
    search: Optional[str] = Query(None, description="Text search"),
    hours: Optional[int] = Query(None, ge=1, le=168, description="Limit to last N hours"),
):
    """Get paginated Zeek log entries with optional filters."""
    filters = {}

    if ip:
        filters["ip"] = ip
    if port:
        filters["port"] = port
    if proto:
        filters["proto"] = proto
    if search:
        filters["search"] = search
    if hours:
        filters["start_time"] = datetime.now() - timedelta(hours=hours)

    result = get_log_entries(log_type, page, per_page, filters)

    return {
        "entries": result.entries,
        "total": result.total,
        "page": result.page,
        "per_page": result.per_page,
        "total_pages": (result.total + result.per_page - 1) // result.per_page,
        "log_type": result.log_type,
    }


@router.get("/logs/{log_type}/{uid}")
async def get_log_detail(
    log_type: str,
    uid: str,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Get a single log entry by UID."""
    entry = get_log_entry_by_uid(log_type, uid)

    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    return {"entry": entry}


@router.post("/search")
async def search_zeek_logs(
    request: SearchRequest,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Search across Zeek logs."""
    results = search_logs(
        query=request.query,
        log_types=request.log_types,
        limit=request.limit,
        hours=request.hours,
    )

    return {"results": results, "count": len(results)}


@router.get("/stats/dns")
async def dns_statistics(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
):
    """Get DNS statistics for the specified time period."""
    stats = get_dns_stats(hours)
    return stats


@router.get("/stats/trends")
async def connection_trends(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
    interval: int = Query(15, ge=5, le=60, description="Bucket interval in minutes"),
):
    """Get connection count trends over time."""
    trends = get_connection_trends(hours, interval)
    return {"trends": trends, "hours": hours, "interval_minutes": interval}


@router.get("/stats/services")
async def service_distribution(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
):
    """Get service distribution from connection logs."""
    services = get_service_distribution(hours)
    return {"services": services, "hours": hours}
