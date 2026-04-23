"""Extractor module — Bilibili URL validation, metadata extraction, and subtitle download."""

from __future__ import annotations

import re
import asyncio
import structlog
from typing import Any

import httpx
import yt_dlp

from app.config import settings
from app.schemas.pipeline import ExtractResult
from app.schemas.job import TranscriptSegmentOut

logger = structlog.get_logger(__name__)

# ── URL Patterns ────────────────────────────────────────────────

# Matches BV IDs like BV1uv411q7Mv (BV + 10 alphanumeric chars)
BVID_PATTERN = re.compile(r"(BV[a-zA-Z0-9]{10})")
BILIBILI_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]{10})"
)
SHORT_LINK_PATTERN = re.compile(r"https?://b23\.tv/([a-zA-Z0-9]+)")


class ExtractionError(Exception):
    """Raised when video extraction fails."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def validate_and_extract_bvid(url: str) -> str:
    """Validate a Bilibili URL and extract the BVID.

    Supports:
    - https://www.bilibili.com/video/BV1xxxxxxxxx
    - https://www.bilibili.com/video/BV1xxxxxxxxx?p=2&t=30
    - https://b23.tv/xxxxx (short links must be resolved separately)
    - Raw BVID strings

    Returns:
        The BVID string (e.g., "BV1uv411q7Mv")

    Raises:
        ExtractionError: If the URL is invalid or not a Bilibili URL
    """
    url = url.strip()

    if not url:
        raise ExtractionError("INVALID_URL", "URL cannot be empty")

    # Direct BVID match
    if re.match(r"^BV[a-zA-Z0-9]{10}$", url):
        return url

    # Full Bilibili URL
    match = BILIBILI_URL_PATTERN.search(url)
    if match:
        return match.group(1)

    # Short link — need to resolve
    if SHORT_LINK_PATTERN.match(url):
        return "__SHORT_LINK__"  # Marker; resolved in async context

    # Check if it looks like a Bilibili URL but malformed
    if "bilibili" in url.lower():
        raise ExtractionError(
            "INVALID_URL",
            f"URL appears to be Bilibili but BVID could not be extracted: {url}",
        )

    raise ExtractionError(
        "INVALID_URL",
        f"Not a valid Bilibili URL. Expected: bilibili.com/video/BVxxxxxxxxxx — got: {url}",
    )


async def resolve_short_link(url: str) -> str:
    """Resolve a b23.tv short link to a full Bilibili URL and extract BVID."""
    logger.info("resolving_short_link", url=url)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            resp = await client.head(url)
            final_url = str(resp.url)
            logger.info("short_link_resolved", final_url=final_url)
            match = BILIBILI_URL_PATTERN.search(final_url)
            if match:
                return match.group(1)
            raise ExtractionError(
                "INVALID_URL",
                f"Short link resolved to non-Bilibili URL: {final_url}",
            )
    except httpx.HTTPError as e:
        raise ExtractionError("INVALID_URL", f"Failed to resolve short link: {e}")


def _build_yt_dlp_opts() -> dict[str, Any]:
    """Build yt-dlp options with optional cookie authentication."""
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        # Add a modern browser User-Agent to bypass some bot detection
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Some Bilibili videos need specific extractor flags
        "extractor_args": {
            "bilibili": ["page_index=1"]
        }
    }

    # Cookie-based authentication for restricted content
    if settings.bilibili_cookies_file:
        opts["cookiefile"] = settings.bilibili_cookies_file
    elif settings.bilibili_sessdata:
        # Build a minimal cookie string
        if opts.get("http_headers"):
            opts["http_headers"]["Cookie"] = f"SESSDATA={settings.bilibili_sessdata}"
        else:
            opts["http_headers"] = {
                "Cookie": f"SESSDATA={settings.bilibili_sessdata}",
            }

    return opts


async def extract_metadata(bvid: str) -> dict[str, Any]:
    """Extract video metadata using yt-dlp.

    Returns a dict with title, author, thumbnail, duration, etc.
    """
    url = f"https://www.bilibili.com/video/{bvid}"
    opts = _build_yt_dlp_opts()
    opts["skip_download"] = True

    logger.info("extracting_metadata", bvid=bvid)

    def _extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as e:
                error_str = str(e).lower()
                if "404" in error_str or "not found" in error_str:
                    raise ExtractionError("VIDEO_NOT_FOUND", f"Video {bvid} not found on Bilibili")
                if "403" in error_str or "login" in error_str:
                    raise ExtractionError(
                        "VIDEO_RESTRICTED",
                        f"Video {bvid} requires login or is geo-restricted",
                    )
                raise ExtractionError("EXTRACTION_FAILED", f"Failed to extract video info: {e}")

    info = await asyncio.to_thread(_extract)
    if info is None:
        raise ExtractionError("EXTRACTION_FAILED", f"yt-dlp returned no info for {bvid}")

    return info


def _parse_yt_dlp_subtitles(info: dict[str, Any]) -> list[TranscriptSegmentOut] | None:
    """Try to extract subtitle segments from yt-dlp metadata.

    Bilibili subtitles are typically in the 'subtitles' or 'automatic_captions' field
    as JSON with 'body' containing segments.
    """
    # Check for manual subtitles first, then auto-generated
    for sub_key in ("subtitles", "automatic_captions"):
        subs = info.get(sub_key, {})
        if not subs:
            continue

        # Look for Chinese subtitle tracks first, then any available
        for lang_code in ("zh-Hans", "zh-CN", "zh", "ai-zh", "en"):
            if lang_code not in subs:
                continue

            tracks = subs[lang_code]
            for track in tracks:
                # Prefer JSON format
                if track.get("ext") == "json":
                    return _download_subtitle_track(track["url"])

    return None


def _download_subtitle_track(url: str) -> list[TranscriptSegmentOut] | None:
    """Download and parse a subtitle JSON track from Bilibili."""
    import httpx as httpx_sync

    try:
        resp = httpx_sync.get(url, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        # Bilibili subtitle JSON format: {"body": [{"from": 0.0, "to": 5.0, "content": "..."}]}
        body = data.get("body", [])
        if not body:
            return None

        segments = []
        for item in body:
            segments.append(
                TranscriptSegmentOut(
                    start=float(item.get("from", 0)),
                    end=float(item.get("to", 0)),
                    text=str(item.get("content", "")),
                )
            )

        return segments if segments else None

    except Exception as e:
        logger.warning("subtitle_download_failed", url=url, error=str(e))
        return None


async def extract_subtitles(bvid: str, info: dict[str, Any]) -> list[TranscriptSegmentOut] | None:
    """Attempt to extract subtitles from the video metadata.

    Tries yt-dlp embedded subtitle data first. If no subtitles are found,
    attempts to download them separately.
    """
    logger.info("extracting_subtitles", bvid=bvid)

    # Method 1: Parse from yt-dlp info dict
    segments = _parse_yt_dlp_subtitles(info)
    if segments:
        logger.info("subtitles_found_in_metadata", bvid=bvid, count=len(segments))
        return segments

    # Method 2: Try downloading with --write-subs explicitly
    url = f"https://www.bilibili.com/video/{bvid}"
    opts = _build_yt_dlp_opts()
    opts.update({
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["zh-Hans", "zh-CN", "zh", "ai-zh", "en"],
        "subtitlesformat": "json3/json/vtt/srt",
    })

    def _try_subs():
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except Exception:
                return None

    info2 = await asyncio.to_thread(_try_subs)
    if info2:
        segments = _parse_yt_dlp_subtitles(info2)
        if segments:
            logger.info("subtitles_found_via_write_subs", bvid=bvid, count=len(segments))
            return segments

    logger.info("no_subtitles_available", bvid=bvid)
    return None


async def extract(url: str) -> ExtractResult:
    """Full extraction pipeline: validate URL → metadata → subtitles.

    This is the main entry point for the extractor module.
    """
    # Step 1: Validate URL and extract BVID
    bvid = validate_and_extract_bvid(url)

    if bvid == "__SHORT_LINK__":
        bvid = await resolve_short_link(url)

    # Step 2: Extract metadata
    info = await extract_metadata(bvid)

    # Step 3: Try to get subtitles
    subtitles = await extract_subtitles(bvid, info)

    # Parse metadata into structured result
    # Handle multi-part videos (pages)
    pages = info.get("entries") or info.get("pages") or []
    page_count = len(pages) if pages else 1

    return ExtractResult(
        bvid=bvid,
        title=info.get("title", "Unknown Title"),
        author=info.get("uploader", info.get("channel", "Unknown Author")),
        thumbnail_url=info.get("thumbnail", ""),
        duration_seconds=int(info.get("duration", 0)),
        view_count=int(info.get("view_count", 0)),
        publish_date=info.get("upload_date", ""),
        description=info.get("description", ""),
        page_count=page_count,
        subtitles=subtitles,
        has_subtitles=subtitles is not None and len(subtitles) > 0,
    )
