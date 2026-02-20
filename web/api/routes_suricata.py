"""Suricata EVE log browsing API endpoints."""

from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from core.auth import verify_credentials
from core.suricata_parser import get_available_event_types, get_eve_entries

router = APIRouter()


@router.get("/events")
async def list_event_types(user: Annotated[str, Depends(verify_credentials)]):
    """List available Suricata EVE event types with counts."""
    events = get_available_event_types()
    return {"events": events}


@router.get("/events/{event_type}")
async def get_events(
    event_type: str,
    user: Annotated[str, Depends(verify_credentials)],
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    ip: Optional[str] = Query(None, description="Filter by source or destination IP"),
    port: Optional[int] = Query(None, description="Filter by port"),
    proto: Optional[str] = Query(None, description="Filter by protocol"),
    search: Optional[str] = Query(None, description="Text search"),
    hours: Optional[int] = Query(None, ge=1, le=168, description="Limit to last N hours"),
):
    """Get paginated Suricata EVE log entries with optional filters."""
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

    result = get_eve_entries(event_type, page, per_page, filters)

    return {
        "entries": result.entries,
        "total": result.total,
        "page": result.page,
        "per_page": result.per_page,
        "total_pages": max(1, (result.total + result.per_page - 1) // result.per_page),
        "event_type": result.event_type,
    }
