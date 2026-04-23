"""Export router — download results in various formats."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Job, Transcript, SummaryResult
from app.modules import exporter
from app.routers.jobs import build_job_result_model

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/export", tags=["export"])


@router.get("/{job_id}/{format}")
async def export_job(
    job_id: str,
    format: str,
    db: AsyncSession = Depends(get_db),
):
    """Export a completed job's results in the specified format.

    Supported formats: markdown, txt, json
    """
    if format not in ("markdown", "txt", "json"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FORMAT",
                    "message": f"Unsupported format: {format}. Use: markdown, txt, json",
                }
            },
        )

    # Get the full result (reuse the result endpoint logic)
    result = await build_job_result_model(job_id, db)

    # Get BVID for filename
    job = await db.get(Job, job_id)
    bvid = job.bvid if job else "export"
    safe_title = "".join(c for c in (job.title or bvid) if c.isalnum() or c in " _-")[:50]

    if format == "markdown":
        content = exporter.export_markdown(result)
        filename = f"{safe_title}_notes.md"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    elif format == "txt":
        content = exporter.export_txt(result)
        filename = f"{safe_title}_notes.txt"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    elif format == "json":
        content = exporter.export_json(result)
        filename = f"{safe_title}_notes.json"
        return Response(
            content=content.encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
