"""Capture management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.auth import verify_credentials, require_admin
from core.capture_manager import (
    start_capture,
    stop_capture,
    get_capture_status,
    delete_pcap_file,
    delete_pcap_files,
    delete_all_pcap_files,
)

router = APIRouter()


class DeleteFilesRequest(BaseModel):
    filenames: list[str]


@router.get("/status")
async def capture_status(user: Annotated[str, Depends(verify_credentials)]):
    """Get capture status and recent files."""
    return get_capture_status()


@router.post("/start")
async def capture_start(user: Annotated[str, Depends(verify_credentials)]):
    """Start packet capture."""
    return start_capture()


@router.post("/stop")
async def capture_stop(user: Annotated[str, Depends(verify_credentials)]):
    """Stop packet capture."""
    return stop_capture()


@router.delete("/files/{filename:path}")
async def delete_capture_file(
    filename: str,
    user: Annotated[str, Depends(require_admin)],
):
    """Delete a single capture file (admin only)."""
    return delete_pcap_file(filename)


@router.post("/files/delete")
async def delete_capture_files(
    body: DeleteFilesRequest,
    user: Annotated[str, Depends(require_admin)],
):
    """Delete multiple capture files (admin only)."""
    return delete_pcap_files(body.filenames)


@router.delete("/files")
async def delete_all_captures(
    user: Annotated[str, Depends(require_admin)],
):
    """Delete all capture files (admin only)."""
    return delete_all_pcap_files()
