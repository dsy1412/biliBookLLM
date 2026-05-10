"""Pipeline orchestrator: coordinates extraction and transcript generation for a job."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Transcript, TranscriptSegment
from app.modules import extractor, transcriber
from app.modules.extractor import ExtractionError
from app.modules.transcriber import TranscriptionError

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
    """Run the extraction and transcript pipeline for a job."""
    start_time = time.time()

    job = await session.get(Job, job_id)
    if job is None:
        logger.error("job_not_found", job_id=job_id)
        return

    logger.info("pipeline_start", job_id=job_id, url=job.url)

    try:
        await _update_job(session, job, "extracting", 5, "Inspecting video metadata")
        extract_result = await extractor.extract(job.url)

        await _update_job(
            session,
            job,
            "extracting",
            15,
            "Checking official Bilibili subtitles",
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

        if extract_result.has_subtitles and not job.force_asr:
            transcript_source = extract_result.subtitle_source or "subtitle-official"
            stage_label = {
                "subtitle-ai": "Using official Bilibili AI captions",
                "subtitle-official": "Using official Bilibili subtitles",
                "subtitle-ydlp": "Using subtitle fallback",
            }.get(transcript_source, "Using subtitles")
            await _update_job(
                session,
                job,
                "transcribing",
                25,
                stage_label,
                transcript_source=transcript_source,
            )
            segments = extract_result.subtitles or []
            whisper_model_used = None
            logger.info(
                "using_subtitles",
                bvid=job.bvid,
                transcript_source=transcript_source,
                segment_count=len(segments),
            )
        else:
            await _update_job(
                session,
                job,
                "downloading_audio",
                20,
                "Downloading audio for local transcription",
                transcript_source="asr",
            )
            transcribe_result = await transcriber.transcribe(
                extract_result.bvid,
                model_name=job.whisper_model,
            )
            segments = transcribe_result.segments
            transcript_source = "asr"
            whisper_model_used = transcribe_result.whisper_model
            logger.info("using_asr", bvid=job.bvid, segment_count=len(segments))

        await _update_job(
            session,
            job,
            "transcribing",
            40,
            "Saving transcript",
            transcript_source=transcript_source,
            whisper_model=whisper_model_used,
        )

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

        for index, seg in enumerate(segments):
            session.add(
                TranscriptSegment(
                    transcript_id=transcript.id,
                    index=index,
                    start_time=seg.start,
                    end_time=seg.end,
                    text=seg.text,
                )
            )
        await session.commit()

        elapsed = round(time.time() - start_time, 2)
        await _update_job(
            session,
            job,
            "completed",
            100,
            None,
            completed_at=datetime.now(timezone.utc),
        )

        logger.info(
            "pipeline_complete",
            job_id=job_id,
            elapsed_seconds=elapsed,
            transcript_source=transcript_source,
            segment_count=len(segments),
        )

    except (ExtractionError, TranscriptionError) as exc:
        logger.error("pipeline_error", job_id=job_id, code=exc.code, message=exc.message)
        await _update_job(
            session,
            job,
            "failed",
            job.progress,
            None,
            error_code=exc.code,
            error_message=exc.message,
        )
    except Exception as exc:
        logger.exception("pipeline_unexpected_error", job_id=job_id)
        await _update_job(
            session,
            job,
            "failed",
            job.progress,
            None,
            error_code="INTERNAL_ERROR",
            error_message=str(exc)[:1000],
        )
