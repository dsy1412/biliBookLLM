"""Jobs router: CRUD and pipeline trigger for processing jobs."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import AsyncSessionLocal, get_db
from app.models import Job, Transcript
from app.modules.extractor import ExtractionError, validate_and_extract_bvid
from app.schemas.job import (
    ChapterOut,
    ErrorDetail,
    JobCreateBatchItem,
    JobCreateBatchRequest,
    JobCreateBatchResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobListItem,
    JobListResponse,
    JobResultResponse,
    JobStatusResponse,
    ProcessingInfo,
    QAPairOut,
    SummaryOut,
    TranscriptOut,
    TranscriptSegmentOut,
    VideoMetadata,
)
from app.services.pipeline import run_pipeline

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


async def _run_pipeline_in_background(job_id: str):
    """Run the pipeline with its own database session."""
    async with AsyncSessionLocal() as session:
        await run_pipeline(job_id, session)


async def _create_or_reuse_job(url: str, options, db: AsyncSession) -> tuple[Job, bool]:
    """Create a new job or reuse an existing one for the same BVID."""
    bvid = validate_and_extract_bvid(url)

    if bvid == "__SHORT_LINK__":
        bvid = f"PENDING_{hash(url) % 10**8:08d}"

    existing = await db.execute(select(Job).where(Job.bvid == bvid))
    existing_job = existing.scalar_one_or_none()

    if existing_job:
        if existing_job.status != "failed":
            return existing_job, True
        await db.delete(existing_job)
        await db.commit()

    job = Job(
        bvid=bvid,
        url=url,
        force_asr=options.force_asr,
        whisper_model=options.whisper_model,
        generate_qa=options.generate_qa,
        llm_model=options.llm_model,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    logger.info("job_created", job_id=job.id, bvid=bvid, url=url)
    asyncio.create_task(_run_pipeline_in_background(job.id))
    return job, False


@router.post("", response_model=JobCreateResponse, status_code=202)
async def create_job(
    request: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a Bilibili video URL for processing."""
    try:
        job, reused_existing = await _create_or_reuse_job(request.url, request.options, db)
    except ExtractionError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": exc.code, "message": exc.message}},
        )

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at.isoformat(),
        url=job.url,
        reused_existing=reused_existing,
    )


@router.post("/batch", response_model=JobCreateBatchResponse, status_code=202)
async def create_jobs_batch(
    request: JobCreateBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit multiple Bilibili URLs in one request."""
    items: list[JobCreateBatchItem] = []

    for url in request.urls:
        try:
            job, reused_existing = await _create_or_reuse_job(url, request.options, db)
            items.append(
                JobCreateBatchItem(
                    url=url,
                    job_id=job.id,
                    status=job.status,
                    created_at=job.created_at.isoformat(),
                    reused_existing=reused_existing,
                )
            )
        except ExtractionError as exc:
            items.append(
                JobCreateBatchItem(
                    url=url,
                    status="invalid",
                    error=ErrorDetail(code=exc.code, message=exc.message),
                )
            )

    return JobCreateBatchResponse(items=items)


async def build_job_result_model(job_id: str, db: AsyncSession) -> JobResultResponse:
    """Build JobResultResponse for the HTTP route and export endpoints."""
    result = await db.execute(
        select(Job)
        .options(
            selectinload(Job.transcript).selectinload(Transcript.segments),
            selectinload(Job.summary_result),
        )
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "JOB_NOT_COMPLETE",
                    "message": f"Job is not yet completed (status: {job.status})",
                    "details": {"status": job.status, "progress": job.progress},
                }
            },
        )

    if not job.transcript:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Job completed but transcript is missing",
                }
            },
        )

    transcript_segments = [
        TranscriptSegmentOut(
            start=float(seg.start_time or 0.0),
            end=float(seg.end_time or 0.0),
            text=seg.text or "",
        )
        for seg in job.transcript.segments
    ]

    summary_out = SummaryOut(
        overall="",
        chapters=[],
        key_takeaways=[],
        keywords=[],
        qa=None,
    )

    llm_model = None
    total_chunks = 0
    processing_seconds = round((job.updated_at - job.created_at).total_seconds(), 2)

    if job.summary_result:
        sr = job.summary_result
        ch_rows = sr.chapters or []
        chapter_out: list[ChapterOut] = []
        for ch in ch_rows if isinstance(ch_rows, list) else []:
            if not isinstance(ch, dict):
                continue
            try:
                chapter_out.append(ChapterOut(**ch))
            except Exception:
                chapter_out.append(
                    ChapterOut(
                        title=str(ch.get("title") or ""),
                        start=float(ch.get("start") or 0.0),
                        end=float(ch.get("end") or 0.0),
                        summary=str(ch.get("summary") or ""),
                    )
                )
        qa_out: list[QAPairOut] | None = None
        if sr.qa_pairs and isinstance(sr.qa_pairs, list):
            qa_list: list[QAPairOut] = []
            for qa in sr.qa_pairs:
                if not isinstance(qa, dict):
                    continue
                try:
                    qa_list.append(QAPairOut(**qa))
                except Exception:
                    qa_list.append(
                        QAPairOut(
                            question=str(qa.get("question") or ""),
                            answer=str(qa.get("answer") or ""),
                        )
                    )
            qa_out = qa_list or None

        summary_out = SummaryOut(
            overall=sr.overall_summary or "",
            chapters=chapter_out,
            key_takeaways=(sr.key_takeaways or []) if isinstance(sr.key_takeaways, list) else [],
            keywords=(sr.keywords or []) if isinstance(sr.keywords, list) else [],
            qa=qa_out,
        )
        llm_model = sr.llm_model
        total_chunks = int(sr.total_chunks or 0)
        ps = sr.processing_seconds
        processing_seconds = float(ps) if ps is not None else 0.0

    return JobResultResponse(
        job_id=job.id,
        metadata=VideoMetadata(
            title=job.title or "",
            author=job.author or "",
            thumbnail_url=job.thumbnail_url or "",
            duration_seconds=job.duration_seconds or 0,
            view_count=job.view_count or 0,
            publish_date=job.publish_date or "",
            bvid=job.bvid,
            page_count=int(job.page_count) if job.page_count is not None else 1,
        ),
        transcript=TranscriptOut(
            source=job.transcript.source or "unknown",
            language=job.transcript.language or "und",
            segments=transcript_segments,
            full_text=job.transcript.full_text or "",
        ),
        summary=summary_out,
        processing_info=ProcessingInfo(
            transcript_source=job.transcript_source or "unknown",
            whisper_model=job.whisper_model,
            llm_model=llm_model,
            total_duration_seconds=processing_seconds,
            segment_count=int(job.transcript.segment_count or 0),
            chunk_count=total_chunks,
        ),
    )


@router.get("/{job_id}/result")
async def get_job_result(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the full result of a completed job."""
    try:
        out = await build_job_result_model(job_id, db)
        return Response(
            content=out.model_dump_json().encode("utf-8"),
            media_type="application/json; charset=utf-8",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_job_result_failed", job_id=job_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "error": {
                        "code": "RESULT_BUILD_ERROR",
                        "message": str(exc)[:2000],
                    }
                }
            },
        )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the current status and metadata of a processing job."""
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
        )

    metadata = None
    if job.title:
        metadata = VideoMetadata(
            title=job.title,
            author=job.author or "",
            thumbnail_url=job.thumbnail_url or "",
            duration_seconds=job.duration_seconds or 0,
            view_count=job.view_count or 0,
            publish_date=job.publish_date or "",
            bvid=job.bvid,
            page_count=int(job.page_count) if job.page_count is not None else 1,
        )

    error = None
    if job.error_code:
        error = ErrorDetail(code=job.error_code, message=job.error_message or "")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        metadata=metadata,
        transcript_source=job.transcript_source,
        error=error,
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all processing jobs with pagination and optional status filter."""
    query = select(Job)
    count_query = select(func.count(Job.id))

    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Job.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        total=total,
        jobs=[
            JobListItem(
                job_id=j.id,
                status=j.status,
                bvid=j.bvid,
                url=j.url,
                title=j.title,
                created_at=j.created_at.isoformat(),
                updated_at=j.updated_at.isoformat(),
                progress=int(j.progress or 0),
                stage=j.stage,
                transcript_source=j.transcript_source,
                error=ErrorDetail(code=j.error_code, message=j.error_message or "")
                if j.error_code
                else None,
            )
            for j in jobs
        ],
    )


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a job and all associated data."""
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
        )

    await db.delete(job)
    await db.commit()
    logger.info("job_deleted", job_id=job_id)
