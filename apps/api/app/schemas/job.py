"""Pydantic request/response schemas for the Jobs API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Request Schemas ─────────────────────────────────────────────


class JobOptions(BaseModel):
    force_asr: bool = False
    whisper_model: str = "base"
    generate_qa: bool = True
    llm_model: str | None = None


class JobCreateRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Bilibili video URL")
    options: JobOptions = Field(default_factory=JobOptions)


# ── Response Schemas ────────────────────────────────────────────


class VideoMetadata(BaseModel):
    title: str
    author: str
    thumbnail_url: str
    duration_seconds: int
    view_count: int
    publish_date: str
    bvid: str
    page_count: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    url: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    stage: str | None
    created_at: str
    updated_at: str
    metadata: VideoMetadata | None = None
    transcript_source: str | None = None
    error: ErrorDetail | None = None


class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str


class TranscriptOut(BaseModel):
    source: str
    language: str
    segments: list[TranscriptSegmentOut]
    full_text: str


class ChapterOut(BaseModel):
    title: str
    start: float
    end: float
    summary: str


class QAPairOut(BaseModel):
    question: str
    answer: str


class SummaryOut(BaseModel):
    overall: str
    chapters: list[ChapterOut]
    key_takeaways: list[str]
    keywords: list[str]
    qa: list[QAPairOut] | None = None


class ProcessingInfo(BaseModel):
    transcript_source: str
    whisper_model: str | None
    # No summarization step in pipeline / no summary in DB => None
    llm_model: str | None = None
    total_duration_seconds: float
    segment_count: int
    chunk_count: int


class JobResultResponse(BaseModel):
    job_id: str
    metadata: VideoMetadata
    transcript: TranscriptOut
    summary: SummaryOut
    processing_info: ProcessingInfo


class JobListItem(BaseModel):
    job_id: str
    status: str
    bvid: str
    title: str | None
    created_at: str
    transcript_source: str | None


class JobListResponse(BaseModel):
    total: int
    jobs: list[JobListItem]
