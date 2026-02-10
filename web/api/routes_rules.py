"""Suricata rules management API endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.auth import verify_credentials, require_admin
from core.rules_manager import (
    list_rules,
    get_rule,
    set_rule_enabled,
    set_rule_threshold,
    remove_rule_threshold,
    get_classtypes,
    reload_suricata,
    get_rule_stats,
)

router = APIRouter()


class RuleStateRequest(BaseModel):
    enabled: bool


class RuleThresholdRequest(BaseModel):
    threshold_type: str = "limit"
    track: str = "by_src"
    count: int = 1
    seconds: int = 60


@router.get("/")
async def get_rules(
    user: Annotated[str, Depends(verify_credentials)],
    search: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
    classtype: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    """List Suricata rules with optional filtering."""
    rules = list_rules(search=search, enabled_only=enabled_only, classtype=classtype, limit=limit)
    return {"rules": rules, "count": len(rules)}


@router.get("/stats")
async def rules_stats(user: Annotated[str, Depends(verify_credentials)]):
    """Get rule statistics."""
    return get_rule_stats()


@router.get("/classtypes")
async def get_rule_classtypes(user: Annotated[str, Depends(verify_credentials)]):
    """Get list of available classtypes."""
    classtypes = get_classtypes()
    return {"classtypes": classtypes}


@router.get("/{sid}")
async def get_rule_details(
    sid: int,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Get details of a specific rule."""
    rule = get_rule(sid)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/{sid}/state")
async def update_rule_state(
    sid: int,
    body: RuleStateRequest,
    user: Annotated[str, Depends(require_admin)],
):
    """Enable or disable a rule (admin only)."""
    success, message = set_rule_enabled(sid, body.enabled)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.put("/{sid}/threshold")
async def update_rule_threshold(
    sid: int,
    body: RuleThresholdRequest,
    user: Annotated[str, Depends(require_admin)],
):
    """Set threshold for a rule (admin only)."""
    success, message = set_rule_threshold(
        sid,
        threshold_type=body.threshold_type,
        track=body.track,
        count=body.count,
        seconds=body.seconds,
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.delete("/{sid}/threshold")
async def delete_rule_threshold(
    sid: int,
    user: Annotated[str, Depends(require_admin)],
):
    """Remove threshold from a rule (admin only)."""
    success, message = remove_rule_threshold(sid)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.post("/reload")
async def reload_rules(user: Annotated[str, Depends(require_admin)]):
    """Reload Suricata to apply rule changes (admin only)."""
    success, message = reload_suricata()
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"success": True, "message": message}
