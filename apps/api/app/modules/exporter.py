"""Exporter module — render results as Markdown, TXT, and JSON."""

from __future__ import annotations

from datetime import datetime

import structlog

from app.schemas.job import JobResultResponse

logger = structlog.get_logger(__name__)


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def export_markdown(result: JobResultResponse) -> str:
    """Render the full result as a Markdown document with YAML front-matter."""
    meta = result.metadata
    summary = result.summary
    transcript = result.transcript

    lines = [
        "---",
        f"title: \"{meta.title}\"",
        f"author: \"{meta.author}\"",
        f"source: \"https://www.bilibili.com/video/{meta.bvid}\"",
        f"duration: {_format_timestamp(meta.duration_seconds)}",
        f"generated: \"{datetime.now().isoformat()}\"",
        f"transcript_source: \"{result.processing_info.transcript_source}\"",
        f"llm_model: \"{result.processing_info.llm_model}\"",
        "---",
        "",
        f"# {meta.title}",
        "",
        f"**Author**: {meta.author}  ",
        f"**Duration**: {_format_timestamp(meta.duration_seconds)}  ",
        f"**Source**: [Bilibili](https://www.bilibili.com/video/{meta.bvid})  ",
        "",
        "---",
        "",
        "## 📝 Overall Summary",
        "",
        summary.overall,
        "",
    ]

    # Chapters
    if summary.chapters:
        lines.append("## 📑 Chapters")
        lines.append("")
        for ch in summary.chapters:
            ts = _format_timestamp(ch.start)
            lines.append(f"### {ch.title} ({ts})")
            lines.append("")
            lines.append(ch.summary)
            lines.append("")

    # Key Takeaways
    if summary.key_takeaways:
        lines.append("## 💡 Key Takeaways")
        lines.append("")
        for takeaway in summary.key_takeaways:
            lines.append(f"- {takeaway}")
        lines.append("")

    # Keywords
    if summary.keywords:
        lines.append("## 🏷️ Keywords")
        lines.append("")
        lines.append(", ".join(f"`{kw}`" for kw in summary.keywords))
        lines.append("")

    # Q&A
    if summary.qa:
        lines.append("## ❓ Q&A")
        lines.append("")
        for qa in summary.qa:
            lines.append(f"**Q: {qa.question}**")
            lines.append("")
            lines.append(f"A: {qa.answer}")
            lines.append("")

    # Full Transcript
    lines.append("---")
    lines.append("")
    lines.append("## 📜 Full Transcript")
    lines.append("")
    for seg in transcript.segments:
        ts = _format_timestamp(seg.start)
        lines.append(f"[{ts}] {seg.text}")
    lines.append("")

    return "\n".join(lines)


def export_txt(result: JobResultResponse) -> str:
    """Render the full result as plain text."""
    meta = result.metadata
    summary = result.summary
    transcript = result.transcript

    lines = [
        "=" * 60,
        meta.title,
        "=" * 60,
        "",
        f"Author: {meta.author}",
        f"Duration: {_format_timestamp(meta.duration_seconds)}",
        f"Source: https://www.bilibili.com/video/{meta.bvid}",
        "",
        "-" * 40,
        "OVERALL SUMMARY",
        "-" * 40,
        "",
        summary.overall,
        "",
    ]

    # Chapters
    if summary.chapters:
        lines.append("-" * 40)
        lines.append("CHAPTERS")
        lines.append("-" * 40)
        lines.append("")
        for ch in summary.chapters:
            ts = _format_timestamp(ch.start)
            lines.append(f"[{ts}] {ch.title}")
            lines.append(ch.summary)
            lines.append("")

    # Key Takeaways
    if summary.key_takeaways:
        lines.append("-" * 40)
        lines.append("KEY TAKEAWAYS")
        lines.append("-" * 40)
        lines.append("")
        for i, takeaway in enumerate(summary.key_takeaways, 1):
            lines.append(f"  {i}. {takeaway}")
        lines.append("")

    # Keywords
    if summary.keywords:
        lines.append("-" * 40)
        lines.append("KEYWORDS")
        lines.append("-" * 40)
        lines.append("")
        lines.append(", ".join(summary.keywords))
        lines.append("")

    # Q&A
    if summary.qa:
        lines.append("-" * 40)
        lines.append("Q&A")
        lines.append("-" * 40)
        lines.append("")
        for qa in summary.qa:
            lines.append(f"Q: {qa.question}")
            lines.append(f"A: {qa.answer}")
            lines.append("")

    # Full Transcript
    lines.append("=" * 60)
    lines.append("FULL TRANSCRIPT")
    lines.append("=" * 60)
    lines.append("")
    for seg in transcript.segments:
        ts = _format_timestamp(seg.start)
        lines.append(f"[{ts}] {seg.text}")
    lines.append("")

    return "\n".join(lines)


def export_json(result: JobResultResponse) -> str:
    """Render the full result as JSON."""
    return result.model_dump_json(indent=2)
