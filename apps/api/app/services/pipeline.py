"""Pipeline orchestrator — coordinates all processing modules for a job."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Transcript, TranscriptSegment, SummaryResult
from app.modules import extractor, transcriber, chunker, summarizer
from app.modules.extractor import ExtractionError
from app.modules.transcriber import TranscriptionError
from app.modules.summarizer import SummarizationError

logger = structlog.get_logger(__name__)


async def _update_job(
    session: AsyncSession,
    job: Job,
    status: str,
    progress: int,
    stage: str | None = None,
    **kwargs,
):
    """Update job status in the database."""
    job.status = status
    job.progress = progress
    job.stage = stage
    for key, value in kwargs.items():
        setattr(job, key, value)
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    logger.info("job_updated", job_id=job.id, status=status, progress=progress, stage=stage)


async def run_pipeline(job_id: str, session: AsyncSession):
    """Run the full processing pipeline for a job.

    Pipeline stages:
    1. Extract metadata + check subtitles
    2. Transcribe (subtitle or ASR fallback)
    3. Chunk transcript
    4. Summarize via LLM
    5. Store results

    This function updates the job status at each stage so the
    frontend can display progress.
    """
    start_time = time.time()

    # Load the job
    job = await session.get(Job, job_id)
    if job is None:
        logger.error("job_not_found", job_id=job_id)
        return

    logger.info("pipeline_start", job_id=job_id, url=job.url)

    try:
        # ── Stage 1: Extract ────────────────────────────────────
        await _update_job(session, job, "extracting", 5, "metadata")

        extract_result = await extractor.extract(job.url)

        # Update job with metadata
        await _update_job(
            session, job, "extracting", 15, "subtitles",
            bvid=extract_result.bvid,
            title=extract_result.title,
            author=extract_result.author,
            thumbnail_url=extract_result.thumbnail_url,
            duration_seconds=extract_result.duration_seconds,
            view_count=extract_result.view_count,
            publish_date=extract_result.publish_date,
            description=extract_result.description,
            page_count=extract_result.page_count,
        )

        # ── Stage 2: Transcribe ─────────────────────────────────
        if extract_result.has_subtitles and not job.force_asr:
            # Subtitle path — fast
            await _update_job(session, job, "transcribing", 25, "subtitle_parse")
            segments = extract_result.subtitles
            transcript_source = "subtitle"
            whisper_model_used = None
            logger.info("using_subtitles", bvid=job.bvid, segment_count=len(segments))
        else:
            # ASR fallback — slower
            await _update_job(session, job, "downloading_audio", 20, "audio_download")
            transcribe_result = await transcriber.transcribe(
                extract_result.bvid,
                model_name=job.whisper_model,
            )
            segments = transcribe_result.segments
            transcript_source = "asr"
            whisper_model_used = transcribe_result.whisper_model
            logger.info("using_asr", bvid=job.bvid, segment_count=len(segments))

        # Update job with transcript source
        await _update_job(
            session, job, "transcribing", 40, "storing_transcript",
            transcript_source=transcript_source,
            whisper_model=whisper_model_used,
        )

        # Store transcript in DB
        full_text = " ".join(seg.text for seg in segments)
        transcript = Transcript(
            job_id=job.id,
            source=transcript_source,
            language="zh-CN",
            full_text=full_text,
            segment_count=len(segments),
        )
        session.add(transcript)
        await session.flush()

        # Store segments
        for i, seg in enumerate(segments):
            db_segment = TranscriptSegment(
                transcript_id=transcript.id,
                index=i,
                start_time=seg.start,
                end_time=seg.end,
                text=seg.text,
            )
            session.add(db_segment)
        await session.commit()

        # ── Done ────────────────────────────────────────────────
        elapsed = round(time.time() - start_time, 2)
        await _update_job(
            session, job, "completed", 100, None,
            completed_at=datetime.now(timezone.utc),
        )

        logger.info(
            "pipeline_complete",
            job_id=job_id,
            elapsed_seconds=elapsed,
            transcript_source=transcript_source,
            segment_count=len(segments),
        )

    except (ExtractionError, TranscriptionError, SummarizationError) as e:
        logger.error("pipeline_error", job_id=job_id, code=e.code, message=e.message)
        await _update_job(
            session, job, "failed", job.progress, None,
            error_code=e.code,
            error_message=e.message,
        )
    except Exception as e:
        logger.exception("pipeline_unexpected_error", job_id=job_id)
        await _update_job(
            session, job, "failed", job.progress, None,
            error_code="INTERNAL_ERROR",
            error_message=str(e)[:1000],
        )
