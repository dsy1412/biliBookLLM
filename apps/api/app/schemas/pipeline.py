"""Internal pipeline DTOs — data passed between pipeline modules."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.job import TranscriptSegmentOut, ChapterOut, QAPairOut


class ExtractResult(BaseModel):
    """Output of the extraction module."""
    bvid: str
    title: str
    author: str
    thumbnail_url: str
    duration_seconds: int
    view_count: int
    publish_date: str
    description: str
    page_count: int
    subtitles: list[TranscriptSegmentOut] | None = None
    has_subtitles: bool = False


class TranscribeResult(BaseModel):
    """Output of the transcription module (subtitle or ASR)."""
    source: str  # "subtitle" or "asr"
    language: str
    segments: list[TranscriptSegmentOut]
    whisper_model: str | None = None


class ChunkResult(BaseModel):
    """Output of the chunking module."""
    chunks: list[str]
    chunk_count: int
    strategy: str  # "chapter_based" or "recursive_split"


class SummarizeResult(BaseModel):
    """Output of the summarization module."""
    overall: str
    chapters: list[ChapterOut]
    key_takeaways: list[str]
    keywords: list[str]
    qa: list[QAPairOut] | None = None
    llm_model: str
    processing_seconds: float
