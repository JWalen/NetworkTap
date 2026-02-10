"""Alert and IDS API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.auth import verify_credentials
from core.config import get_config
from core.alert_parser import parse_suricata_alerts, parse_zeek_alerts

router = APIRouter()


@router.get("/suricata")
async def suricata_alerts(
    user: Annotated[str, Depends(verify_credentials)],
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get recent Suricata alerts."""
    config = get_config()
    alerts = parse_suricata_alerts(config.suricata_eve_log, limit=limit, offset=offset)
    return {"alerts": alerts, "count": len(alerts), "source": "suricata"}


@router.get("/zeek")
async def zeek_alerts(
    user: Annotated[str, Depends(verify_credentials)],
    limit: int = Query(100, ge=1, le=1000),
):
    """Get recent Zeek notices and alerts."""
    config = get_config()
    alerts = parse_zeek_alerts(config.zeek_log_dir, limit=limit)
    return {"alerts": alerts, "count": len(alerts), "source": "zeek"}


@router.get("/all")
async def all_alerts(
    user: Annotated[str, Depends(verify_credentials)],
    limit: int = Query(100, ge=1, le=1000),
):
    """Get combined alerts from all sources."""
    config = get_config()

    suricata = parse_suricata_alerts(config.suricata_eve_log, limit=limit)
    zeek = parse_zeek_alerts(config.zeek_log_dir, limit=limit)

    combined = suricata + zeek
    combined.sort(key=lambda a: a.get("timestamp", ""), reverse=True)

    return {
        "alerts": combined[:limit],
        "count": len(combined[:limit]),
        "sources": {"suricata": len(suricata), "zeek": len(zeek)},
    }
