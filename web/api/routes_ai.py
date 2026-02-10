"""AI and Anomaly Detection API endpoints."""

import asyncio
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.auth import verify_credentials
from core.config import get_config
from core.anomaly_detector import get_detector, AnomalyDetector
from core.ai_assistant import get_assistant, AIAssistant

router = APIRouter()


# ── Anomaly Detection Endpoints ────────────────────────────────────


@router.get("/anomalies")
async def get_anomalies(
    user: Annotated[str, Depends(verify_credentials)],
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent detected anomalies."""
    detector = get_detector()
    anomalies = detector.get_recent_anomalies(limit)
    return {
        "anomalies": anomalies,
        "count": len(anomalies),
    }


@router.get("/anomalies/stats")
async def get_anomaly_stats(user: Annotated[str, Depends(verify_credentials)]):
    """Get anomaly detection statistics and status."""
    detector = get_detector()
    return detector.get_stats()


@router.post("/anomalies/toggle")
async def toggle_anomaly_detection(
    user: Annotated[str, Depends(verify_credentials)],
    enabled: bool = True,
):
    """Enable or disable anomaly detection (runtime only, doesn't persist)."""
    detector = get_detector()
    config = get_config()

    if enabled and not detector._running:
        # Start detection in background
        asyncio.create_task(detector.start())
        return {"success": True, "message": "Anomaly detection started", "enabled": True}
    elif not enabled and detector._running:
        detector.stop()
        return {"success": True, "message": "Anomaly detection stopped", "enabled": False}
    else:
        return {
            "success": True,
            "message": f"Anomaly detection already {'running' if detector._running else 'stopped'}",
            "enabled": detector._running
        }


# ── AI Assistant Endpoints ─────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    include_context: bool = True


class AnalyzeIPRequest(BaseModel):
    ip: str


@router.get("/assistant/status")
async def get_assistant_status(user: Annotated[str, Depends(verify_credentials)]):
    """Check if AI assistant is available."""
    assistant = get_assistant()
    status = await assistant.check_availability()
    return status


@router.post("/assistant/chat")
async def chat_with_assistant(
    request: ChatRequest,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Send a message to the AI assistant."""
    assistant = get_assistant()

    # Build context if requested
    context = None
    if request.include_context:
        context = await _build_chat_context()

    response = await assistant.chat(request.message, context)
    return {"response": response}


@router.post("/assistant/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Stream a response from the AI assistant."""
    assistant = get_assistant()

    context = None
    if request.include_context:
        context = await _build_chat_context()

    async def generate():
        async for token in assistant.chat_stream(request.message, context):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/assistant/summarize")
async def summarize_alerts(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
):
    """Get an AI-generated summary of recent alerts."""
    assistant = get_assistant()
    summary = await assistant.summarize_alerts(hours)
    return {"summary": summary, "hours": hours}


@router.post("/assistant/analyze-ip")
async def analyze_ip(
    request: AnalyzeIPRequest,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Analyze activity for a specific IP address."""
    assistant = get_assistant()
    analysis = await assistant.analyze_ip(request.ip)
    return {"ip": request.ip, "analysis": analysis}


@router.post("/assistant/explain-alert")
async def explain_alert(
    alert: dict,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Get a plain-language explanation of an alert."""
    assistant = get_assistant()
    explanation = await assistant.explain_alert(alert)
    return {"explanation": explanation}


async def _build_chat_context() -> dict:
    """Build context data for the AI assistant."""
    from core.alert_parser import parse_suricata_alerts
    from core.stats_collector import get_traffic_stats

    config = get_config()

    # Gather context in parallel
    try:
        alerts = parse_suricata_alerts(config.suricata_eve_log, limit=20)
    except Exception:
        alerts = []

    try:
        stats = get_traffic_stats(1).to_dict()
    except Exception:
        stats = {}

    detector = get_detector()
    anomalies = detector.get_recent_anomalies(10)

    return {
        "alerts": alerts,
        "stats": stats,
        "anomalies": anomalies,
        "top_talkers": stats.get("top_talkers", [])[:5] if stats else [],
    }


# ── AI Settings Endpoints ──────────────────────────────────────────


@router.get("/settings")
async def get_ai_settings(user: Annotated[str, Depends(verify_credentials)]):
    """Get current AI feature settings."""
    config = get_config()
    detector = get_detector()
    assistant = get_assistant()

    assistant_status = await assistant.check_availability()

    return {
        "anomaly_detection": {
            "enabled": config.anomaly_detection_enabled,
            "running": detector._running,
            "sensitivity": config.anomaly_sensitivity,
            "interval_seconds": config.anomaly_interval,
        },
        "ai_assistant": {
            "enabled": config.ai_assistant_enabled,
            "available": assistant_status.get("available", False),
            "model": config.ollama_model,
            "ollama_url": config.ollama_url,
            "status_detail": assistant_status.get("reason") if not assistant_status.get("available") else None,
        }
    }


@router.post("/assistant/pull-model")
async def pull_model(
    user: Annotated[str, Depends(verify_credentials)],
    model: str = Query(default=None),
):
    """Pull/download a model in Ollama."""
    import httpx

    config = get_config()
    model_name = model or config.ollama_model

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{config.ollama_url}/api/pull",
                json={"name": model_name, "stream": False},
            )
            if resp.status_code == 200:
                return {"success": True, "message": f"Model '{model_name}' pulled successfully"}
            else:
                return {"success": False, "message": f"Failed to pull model: {resp.text}"}
    except httpx.ConnectError:
        return {"success": False, "message": "Cannot connect to Ollama"}
    except httpx.TimeoutException:
        return {"success": False, "message": "Model pull timed out (this can take several minutes for large models)"}
    except Exception as e:
        return {"success": False, "message": str(e)}
