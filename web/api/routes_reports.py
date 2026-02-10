"""Report generation API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel

from core.auth import verify_credentials
from core.report_generator import (
    generate_alerts_csv,
    generate_stats_csv,
    generate_system_report,
    generate_html_report,
    save_report,
    list_reports,
    REPORTS_DIR,
)
from datetime import datetime

router = APIRouter()


@router.get("/alerts.csv")
async def export_alerts_csv(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(10000, ge=1, le=100000),
):
    """Export alerts as CSV."""
    csv_content = generate_alerts_csv(hours, limit)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=networktap_alerts_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )


@router.get("/stats.csv")
async def export_stats_csv(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
):
    """Export traffic statistics as CSV."""
    csv_content = generate_stats_csv(hours)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=networktap_stats_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )


@router.get("/system.json")
async def export_system_json(user: Annotated[str, Depends(verify_credentials)]):
    """Export system report as JSON."""
    report = generate_system_report()
    
    return Response(
        content=__import__("json").dumps(report, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=networktap_system_{datetime.now().strftime('%Y%m%d')}.json"
        }
    )


@router.get("/report.html")
async def export_html_report(
    user: Annotated[str, Depends(verify_credentials)],
    hours: int = Query(24, ge=1, le=168),
):
    """Generate HTML report."""
    html_content = generate_html_report(hours)
    
    return Response(
        content=html_content,
        media_type="text/html",
        headers={
            "Content-Disposition": f"attachment; filename=networktap_report_{datetime.now().strftime('%Y%m%d')}.html"
        }
    )


@router.get("/")
async def get_saved_reports(user: Annotated[str, Depends(verify_credentials)]):
    """List saved reports."""
    reports = list_reports()
    return {"reports": reports, "count": len(reports)}


@router.post("/save")
async def save_new_report(
    user: Annotated[str, Depends(verify_credentials)],
    format: str = Query("html", pattern="^(html|csv|json)$"),
    hours: int = Query(24, ge=1, le=168),
):
    """Generate and save a report."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if format == "html":
        content = generate_html_report(hours)
        filename = f"report_{timestamp}.html"
    elif format == "csv":
        content = generate_alerts_csv(hours)
        filename = f"alerts_{timestamp}.csv"
    else:
        content = __import__("json").dumps(generate_system_report(), indent=2)
        filename = f"system_{timestamp}.json"
    
    path = save_report(content, filename)
    
    return {"success": True, "filename": filename, "path": str(path)}


@router.get("/download/{filename}")
async def download_saved_report(
    filename: str,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Download a saved report."""
    report_path = REPORTS_DIR / filename
    
    if not report_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Determine media type
    if filename.endswith(".html"):
        media_type = "text/html"
    elif filename.endswith(".csv"):
        media_type = "text/csv"
    else:
        media_type = "application/json"
    
    return FileResponse(
        path=str(report_path),
        filename=filename,
        media_type=media_type,
    )
