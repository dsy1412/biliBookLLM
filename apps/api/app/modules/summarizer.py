"""Summarizer module — LLM-powered map-reduce summarization."""

from __future__ import annotations

import asyncio
import json
import time

import structlog
from openai import AsyncOpenAI

from app.config import settings
from app.schemas.pipeline import SummarizeResult
from app.schemas.job import ChapterOut, QAPairOut

logger = structlog.get_logger(__name__)

# Concurrency limit for parallel LLM calls
MAX_CONCURRENT_LLM_CALLS = 3

# ── Prompt Templates ────────────────────────────────────────────

CHUNK_SUMMARY_SYSTEM_PROMPT = """You are an expert note-taking assistant. You will receive a segment of a video transcript. Your task is to create a concise summary of this segment.

Rules:
1. Write the summary in the SAME LANGUAGE as the transcript (if Chinese, write Chinese; if English, write English).
2. Focus on key information, arguments, and conclusions.
3. Ignore filler words, repetitions, and off-topic remarks.
4. Keep the summary concise but informative (2-4 sentences).
5. Return ONLY the summary text, no headers or formatting."""

CHUNK_SUMMARY_USER_PROMPT = """Please summarize the following transcript segment:

---
{chunk}
---"""

FINAL_SUMMARY_SYSTEM_PROMPT = """You are an expert note-taking assistant. You will receive a list of segment summaries from a video transcript. Your task is to produce a comprehensive structured summary.

You MUST respond with a valid JSON object in this exact format:
{{
  "overall": "A comprehensive overall summary of the entire video (3-5 sentences)",
  "chapters": [
    {{
      "title": "Chapter title",
      "start": 0.0,
      "end": 120.0,
      "summary": "Chapter summary (2-3 sentences)"
    }}
  ],
  "key_takeaways": [
    "Key takeaway 1",
    "Key takeaway 2",
    "Key takeaway 3"
  ],
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}

Rules:
1. Write ALL content in the SAME LANGUAGE as the input summaries.
2. Generate 3-8 chapters that logically divide the content.
3. Generate 3-7 key takeaways.
4. Generate 5-10 keywords/key phrases.
5. Chapter start/end times should be approximate based on segment order.
6. Return ONLY valid JSON, no markdown code fences."""

FINAL_SUMMARY_USER_PROMPT = """Here are the segment summaries from a video with total duration {duration} seconds. The video has {chunk_count} segments.

Segment summaries:
{summaries}

Please generate the structured summary as JSON."""

QA_SYSTEM_PROMPT = """You are an educational content expert. Based on the video summary and key points provided, generate thoughtful Q&A pairs that test understanding of the content.

You MUST respond with a valid JSON array:
[
  {{
    "question": "A meaningful question about the content",
    "answer": "A clear, informative answer"
  }}
]

Rules:
1. Generate 3-5 Q&A pairs.
2. Questions should test understanding, not just recall.
3. Write in the SAME LANGUAGE as the input content.
4. Return ONLY valid JSON array, no markdown code fences."""

QA_USER_PROMPT = """Based on this video summary, generate Q&A pairs:

Overall Summary: {overall}

Key Takeaways:
{takeaways}"""


class SummarizationError(Exception):
    """Raised when summarization fails."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _get_llm_client() -> AsyncOpenAI:
    """Create an OpenAI-compatible async client."""
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base_url,
    )


async def _llm_call(
    client: AsyncOpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    max_retries: int = 3,
) -> str:
    """Make a single LLM API call with retry logic."""
    target_model = model or settings.llm_model

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            content = response.choices[0].message.content
            if content is None:
                raise SummarizationError("LLM_EMPTY", "LLM returned empty response")
            return content.strip()

        except SummarizationError:
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                logger.warning(
                    "llm_call_retry",
                    attempt=attempt + 1,
                    wait_seconds=wait_time,
                    error=str(e),
                )
                await asyncio.sleep(wait_time)
            else:
                raise SummarizationError(
                    "LLM_ERROR",
                    f"LLM API call failed after {max_retries} attempts: {e}",
                )

    # Should never reach here
    raise SummarizationError("LLM_ERROR", "Unexpected error in LLM call loop")


async def _summarize_chunk(
    client: AsyncOpenAI,
    chunk: str,
    chunk_index: int,
    semaphore: asyncio.Semaphore,
    model: str | None = None,
) -> str:
    """Summarize a single chunk (map phase)."""
    async with semaphore:
        logger.debug("summarizing_chunk", index=chunk_index)
        result = await _llm_call(
            client,
            CHUNK_SUMMARY_SYSTEM_PROMPT,
            CHUNK_SUMMARY_USER_PROMPT.format(chunk=chunk),
            model=model,
        )
        logger.debug("chunk_summarized", index=chunk_index, length=len(result))
        return result


async def summarize(
    chunks: list[str],
    duration_seconds: int = 0,
    generate_qa: bool = True,
    model: str | None = None,
) -> SummarizeResult:
    """Full map-reduce summarization pipeline.

    Args:
        chunks: List of transcript chunks to summarize
        duration_seconds: Total video duration for chapter time estimation
        generate_qa: Whether to generate Q&A pairs
        model: LLM model name override

    Returns:
        Structured summary result
    """
    start_time = time.time()
    target_model = model or settings.llm_model
    client = _get_llm_client()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

    logger.info(
        "starting_summarization",
        chunk_count=len(chunks),
        model=target_model,
        generate_qa=generate_qa,
    )

    # ── MAP PHASE: Summarize each chunk in parallel ─────────────

    if len(chunks) == 1:
        # Short transcript — skip map phase, go directly to structured summary
        chunk_summaries = [chunks[0]]
    else:
        tasks = [
            _summarize_chunk(client, chunk, i, semaphore, target_model)
            for i, chunk in enumerate(chunks)
        ]
        chunk_summaries = await asyncio.gather(*tasks)

    logger.info("map_phase_complete", summary_count=len(chunk_summaries))

    # ── REDUCE PHASE: Merge into structured summary ─────────────

    numbered_summaries = "\n".join(
        f"[Segment {i + 1}]: {s}" for i, s in enumerate(chunk_summaries)
    )

    reduce_response = await _llm_call(
        client,
        FINAL_SUMMARY_SYSTEM_PROMPT,
        FINAL_SUMMARY_USER_PROMPT.format(
            duration=duration_seconds,
            chunk_count=len(chunks),
            summaries=numbered_summaries,
        ),
        model=target_model,
    )

    # Parse the structured JSON response
    try:
        # Strip potential markdown code fences
        clean_json = reduce_response.strip()
        if clean_json.startswith("```"):
            clean_json = "\n".join(clean_json.split("\n")[1:-1])
        structured = json.loads(clean_json)
    except json.JSONDecodeError as e:
        logger.error("json_parse_failed", response=reduce_response[:500], error=str(e))
        raise SummarizationError(
            "LLM_PARSE_ERROR",
            f"Failed to parse LLM response as JSON: {e}",
        )

    # Build chapter list with estimated timestamps
    chapters = []
    raw_chapters = structured.get("chapters", [])
    chunk_duration = duration_seconds / max(len(raw_chapters), 1)

    for i, ch in enumerate(raw_chapters):
        chapters.append(
            ChapterOut(
                title=ch.get("title", f"Chapter {i + 1}"),
                start=ch.get("start", i * chunk_duration),
                end=ch.get("end", (i + 1) * chunk_duration),
                summary=ch.get("summary", ""),
            )
        )

    # ── Q&A PHASE (optional) ────────────────────────────────────

    qa_pairs = None
    if generate_qa:
        try:
            takeaways_text = "\n".join(
                f"- {t}" for t in structured.get("key_takeaways", [])
            )
            qa_response = await _llm_call(
                client,
                QA_SYSTEM_PROMPT,
                QA_USER_PROMPT.format(
                    overall=structured.get("overall", ""),
                    takeaways=takeaways_text,
                ),
                model=target_model,
            )

            clean_qa = qa_response.strip()
            if clean_qa.startswith("```"):
                clean_qa = "\n".join(clean_qa.split("\n")[1:-1])
            qa_raw = json.loads(clean_qa)
            qa_pairs = [
                QAPairOut(question=q["question"], answer=q["answer"])
                for q in qa_raw
            ]
        except Exception as e:
            logger.warning("qa_generation_failed", error=str(e))
            qa_pairs = None  # Q&A is optional — don't fail the whole pipeline

    elapsed = time.time() - start_time
    logger.info("summarization_complete", elapsed_seconds=f"{elapsed:.1f}")

    return SummarizeResult(
        overall=structured.get("overall", ""),
        chapters=chapters,
        key_takeaways=structured.get("key_takeaways", []),
        keywords=structured.get("keywords", []),
        qa=qa_pairs,
        llm_model=target_model,
        processing_seconds=round(elapsed, 2),
    )
