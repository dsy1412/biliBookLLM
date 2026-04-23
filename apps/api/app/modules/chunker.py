"""Chunker module — split transcripts into semantically coherent chunks."""

from __future__ import annotations

import structlog

from app.schemas.job import TranscriptSegmentOut
from app.schemas.pipeline import ChunkResult

logger = structlog.get_logger(__name__)

# Default chunking parameters
DEFAULT_CHUNK_SIZE = 800  # tokens (approximate)
DEFAULT_OVERLAP = 80  # tokens (10% overlap)


def estimate_token_count(text: str) -> int:
    """Estimate token count for mixed CJK/Latin text.

    Rough heuristic:
    - CJK characters ≈ 1 token each
    - Latin words ≈ 1.3 tokens each
    - More accurate than just len(text) / 4
    """
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    non_cjk = text
    for c in text:
        if "\u4e00" <= c <= "\u9fff":
            non_cjk = non_cjk.replace(c, "", 1)

    latin_words = len(non_cjk.split())
    return cjk_count + int(latin_words * 1.3)


def chunk_by_segments(
    segments: list[TranscriptSegmentOut],
    max_tokens: int = DEFAULT_CHUNK_SIZE,
    overlap_tokens: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Split transcript segments into chunks respecting token limits.

    Segments are grouped until adding another would exceed max_tokens.
    Overlap is applied by re-including trailing segments from the previous chunk.
    """
    if not segments:
        return []

    chunks: list[str] = []
    current_texts: list[str] = []
    current_tokens = 0

    for segment in segments:
        seg_tokens = estimate_token_count(segment.text)

        # If single segment exceeds limit, it becomes its own chunk
        if seg_tokens > max_tokens:
            if current_texts:
                chunks.append(" ".join(current_texts))
                current_texts = []
                current_tokens = 0
            chunks.append(segment.text)
            continue

        # If adding this segment would exceed limit, finalize current chunk
        if current_tokens + seg_tokens > max_tokens and current_texts:
            chunks.append(" ".join(current_texts))

            # Apply overlap: keep trailing segments that fit within overlap budget
            overlap_texts: list[str] = []
            overlap_count = 0
            for t in reversed(current_texts):
                t_tokens = estimate_token_count(t)
                if overlap_count + t_tokens > overlap_tokens:
                    break
                overlap_texts.insert(0, t)
                overlap_count += t_tokens

            current_texts = overlap_texts
            current_tokens = overlap_count

        current_texts.append(segment.text)
        current_tokens += seg_tokens

    # Don't forget the last chunk
    if current_texts:
        chunks.append(" ".join(current_texts))

    return chunks


def chunk_by_chapters(
    segments: list[TranscriptSegmentOut],
    chapters: list[dict],
    max_tokens: int = DEFAULT_CHUNK_SIZE,
) -> list[str]:
    """Split transcript using chapter boundaries from video metadata.

    Each chapter's segments are grouped. If a chapter exceeds max_tokens,
    it's further split using the segment-based chunker.
    """
    if not chapters:
        return chunk_by_segments(segments, max_tokens)

    chunks: list[str] = []

    for chapter in chapters:
        ch_start = chapter.get("start_time", chapter.get("start", 0))
        ch_end = chapter.get("end_time", chapter.get("end", float("inf")))

        # Collect segments within this chapter's time range
        chapter_segs = [
            s for s in segments if s.start >= ch_start and s.start < ch_end
        ]

        if not chapter_segs:
            continue

        chapter_text = " ".join(s.text for s in chapter_segs)
        chapter_tokens = estimate_token_count(chapter_text)

        if chapter_tokens <= max_tokens:
            chunks.append(chapter_text)
        else:
            # Chapter too long — sub-chunk it
            sub_chunks = chunk_by_segments(chapter_segs, max_tokens)
            chunks.extend(sub_chunks)

    return chunks


def chunk_transcript(
    segments: list[TranscriptSegmentOut],
    chapters: list[dict] | None = None,
    max_tokens: int = DEFAULT_CHUNK_SIZE,
    overlap_tokens: int = DEFAULT_OVERLAP,
) -> ChunkResult:
    """Main entry point for the chunking module.

    Uses chapter-based chunking if chapters are available,
    otherwise falls back to segment-based recursive splitting.
    """
    logger.info(
        "chunking_transcript",
        segment_count=len(segments),
        has_chapters=chapters is not None and len(chapters or []) > 0,
    )

    if chapters:
        chunks = chunk_by_chapters(segments, chapters, max_tokens)
        strategy = "chapter_based"
    else:
        chunks = chunk_by_segments(segments, max_tokens, overlap_tokens)
        strategy = "recursive_split"

    # Filter out empty chunks
    chunks = [c.strip() for c in chunks if c.strip()]

    logger.info("chunking_complete", chunk_count=len(chunks), strategy=strategy)

    return ChunkResult(
        chunks=chunks,
        chunk_count=len(chunks),
        strategy=strategy,
    )
