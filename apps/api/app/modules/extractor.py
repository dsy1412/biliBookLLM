"""Extractor module: Bilibili URL validation, metadata extraction, and subtitle download."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import structlog
import yt_dlp

from app.config import settings
from app.schemas.job import TranscriptSegmentOut
from app.schemas.pipeline import ExtractResult

logger = structlog.get_logger(__name__)

BVID_PATTERN = re.compile(r"(BV[a-zA-Z0-9]{10})")
BILIBILI_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]{10})"
)
SHORT_LINK_PATTERN = re.compile(r"https?://b23\.tv/([a-zA-Z0-9]+)")

TRACK_LANGUAGE_PREFERENCE = (
    "zh-Hans",
    "zh-CN",
    "zh",
    "zh-Hant",
    "ai-zh",
    "en",
)


class ExtractionError(Exception):
    """Raised when video extraction fails."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def validate_and_extract_bvid(url: str) -> str:
    """Validate a Bilibili URL and extract the BVID."""
    url = url.strip()

    if not url:
        raise ExtractionError("INVALID_URL", "URL cannot be empty")

    if re.match(r"^BV[a-zA-Z0-9]{10}$", url):
        return url

    match = BILIBILI_URL_PATTERN.search(url)
    if match:
        return match.group(1)

    if SHORT_LINK_PATTERN.match(url):
        return "__SHORT_LINK__"

    if "bilibili" in url.lower():
        raise ExtractionError(
            "INVALID_URL",
            f"URL appears to be Bilibili but BVID could not be extracted: {url}",
        )

    raise ExtractionError(
        "INVALID_URL",
        f"Not a valid Bilibili URL. Expected: bilibili.com/video/BVxxxxxxxxxx but got: {url}",
    )


def extract_page_number(url: str) -> int:
    """Extract the multi-part page number from the URL query string."""
    if re.match(r"^BV[a-zA-Z0-9]{10}$", url.strip()):
        return 1

    try:
        parsed = urlparse(url)
        raw_page = parse_qs(parsed.query).get("p", ["1"])[0]
        page = int(raw_page)
        return page if page > 0 else 1
    except Exception:
        return 1


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
    except httpx.HTTPError as exc:
        raise ExtractionError("INVALID_URL", f"Failed to resolve short link: {exc}")


def _build_yt_dlp_opts(page_number: int = 1) -> dict[str, Any]:
    """Build yt-dlp options with optional cookie authentication."""
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "extractor_args": {
            "bilibili": [f"page_index={page_number}"],
        },
    }

    if settings.bilibili_cookies_file:
        opts["cookiefile"] = settings.bilibili_cookies_file
    elif settings.bilibili_sessdata:
        opts["http_headers"] = {
            "Cookie": f"SESSDATA={settings.bilibili_sessdata}",
        }

    return opts


async def extract_metadata(bvid: str, page_number: int = 1) -> dict[str, Any]:
    """Extract video metadata using yt-dlp."""
    url = f"https://www.bilibili.com/video/{bvid}"
    opts = _build_yt_dlp_opts(page_number)
    opts["skip_download"] = True

    logger.info("extracting_metadata", bvid=bvid, page_number=page_number)

    def _extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as exc:
                error_str = str(exc).lower()
                if "404" in error_str or "not found" in error_str:
                    raise ExtractionError("VIDEO_NOT_FOUND", f"Video {bvid} not found on Bilibili")
                if "403" in error_str or "login" in error_str:
                    raise ExtractionError(
                        "VIDEO_RESTRICTED",
                        f"Video {bvid} requires login or is geo-restricted",
                    )
                raise ExtractionError("EXTRACTION_FAILED", f"Failed to extract video info: {exc}")

    info = await asyncio.to_thread(_extract)
    if info is None:
        raise ExtractionError("EXTRACTION_FAILED", f"yt-dlp returned no info for {bvid}")

    return info


def _normalize_subtitle_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://"):
        return f"https://{url[len('http://'):]}"
    return url


def _track_is_ai_generated(track: dict[str, Any]) -> bool:
    url = str(track.get("subtitle_url") or track.get("url") or "")
    return (
        "aisubtitle." in url
        or bool(track.get("ai_type"))
        or bool(track.get("is_ai"))
        or str(track.get("type")) == "1"
    )


def _normalize_track(track: dict[str, Any], source: str) -> dict[str, Any] | None:
    subtitle_url = _normalize_subtitle_url(track.get("subtitle_url") or track.get("url"))
    if not subtitle_url:
        return None

    return {
        "source": source,
        "subtitle_url": subtitle_url,
        "lang": track.get("lan") or track.get("lang") or "",
        "lang_doc": track.get("lan_doc") or track.get("lang_doc") or "",
        "is_ai": _track_is_ai_generated(track),
    }


async def _fetch_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
    }
    cookies = {"SESSDATA": settings.bilibili_sessdata} if settings.bilibili_sessdata else None

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers, cookies=cookies) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        logger.warning("bilibili_api_request_failed", url=url, params=params, error=str(exc))
        return None


async def _fetch_official_subtitle_tracks(bvid: str, cid: int | None) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    view_payload = await _fetch_json(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": bvid},
    )
    view_data = view_payload.get("data", {}) if isinstance(view_payload, dict) else {}
    view_subtitles = ((view_data.get("subtitle") or {}).get("list")) or []
    for track in view_subtitles:
        if not isinstance(track, dict):
            continue
        normalized = _normalize_track(track, "view")
        if normalized and normalized["subtitle_url"] not in seen_urls:
            seen_urls.add(normalized["subtitle_url"])
            tracks.append(normalized)

    if cid is None:
        return tracks

    player_wbi_payload = await _fetch_json(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"bvid": bvid, "cid": cid},
    )
    player_wbi_data = player_wbi_payload.get("data", {}) if isinstance(player_wbi_payload, dict) else {}
    player_wbi_subtitles = ((player_wbi_data.get("subtitle") or {}).get("subtitles")) or []
    for track in player_wbi_subtitles:
        if not isinstance(track, dict):
            continue
        normalized = _normalize_track(track, "player_wbi_v2")
        if normalized and normalized["subtitle_url"] not in seen_urls:
            seen_urls.add(normalized["subtitle_url"])
            tracks.append(normalized)

    player_payload = await _fetch_json(
        "https://api.bilibili.com/x/player/v2",
        params={"bvid": bvid, "cid": cid},
    )
    player_data = player_payload.get("data", {}) if isinstance(player_payload, dict) else {}
    player_subtitles = ((player_data.get("subtitle") or {}).get("subtitles")) or []
    for track in player_subtitles:
        if not isinstance(track, dict):
            continue
        normalized = _normalize_track(track, "player_v2")
        if normalized and normalized["subtitle_url"] not in seen_urls:
            seen_urls.add(normalized["subtitle_url"])
            tracks.append(normalized)

    return tracks


def _preferred_track_sort_key(track: dict[str, Any]) -> tuple[int, int, str]:
    lang = str(track.get("lang") or "")
    try:
        lang_rank = TRACK_LANGUAGE_PREFERENCE.index(lang)
    except ValueError:
        lang_rank = len(TRACK_LANGUAGE_PREFERENCE)

    ai_rank = 1 if track.get("is_ai") else 0
    lang_doc = str(track.get("lang_doc") or "")
    return (lang_rank, ai_rank, lang_doc)


def _pick_preferred_track(tracks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tracks:
        return None
    return sorted(tracks, key=_preferred_track_sort_key)[0]


def _download_subtitle_track(url: str) -> list[TranscriptSegmentOut] | None:
    """Download and parse a subtitle JSON track from Bilibili."""
    import httpx as httpx_sync

    try:
        response = httpx_sync.get(url, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        body = data.get("body", [])
        if not body:
            return None

        segments: list[TranscriptSegmentOut] = []
        for item in body:
            segments.append(
                TranscriptSegmentOut(
                    start=float(item.get("from", 0)),
                    end=float(item.get("to", 0)),
                    text=str(item.get("content", "")),
                )
            )

        return segments if segments else None
    except Exception as exc:
        logger.warning("subtitle_download_failed", url=url, error=str(exc))
        return None


def _parse_yt_dlp_subtitles(info: dict[str, Any]) -> tuple[list[TranscriptSegmentOut] | None, dict[str, Any]]:
    """Try to extract subtitle segments from yt-dlp metadata."""
    for sub_key in ("subtitles", "automatic_captions"):
        subs = info.get(sub_key, {})
        if not subs:
            continue

        for lang_code in TRACK_LANGUAGE_PREFERENCE:
            if lang_code not in subs:
                continue

            tracks = subs[lang_code]
            for track in tracks:
                if track.get("ext") != "json":
                    continue
                subtitle_url = _normalize_subtitle_url(track.get("url"))
                if not subtitle_url:
                    continue
                segments = _download_subtitle_track(subtitle_url)
                if not segments:
                    continue
                return segments, {
                    "subtitle_source": "subtitle-ydlp",
                    "subtitle_language": lang_code,
                    "subtitle_track_count": len(tracks),
                    "official_subtitle_available": False,
                }

    return None, {
        "subtitle_source": None,
        "subtitle_language": None,
        "subtitle_track_count": 0,
        "official_subtitle_available": False,
    }


def _pick_requested_page(info: dict[str, Any], page_number: int) -> dict[str, Any] | None:
    entries = info.get("entries")
    if isinstance(entries, list) and entries:
        index = min(max(page_number - 1, 0), len(entries) - 1)
        picked = entries[index]
        if isinstance(picked, dict):
            return picked

    pages = info.get("pages")
    if isinstance(pages, list) and pages:
        index = min(max(page_number - 1, 0), len(pages) - 1)
        picked = pages[index]
        if isinstance(picked, dict):
            return picked

    return info


def _extract_cid(info: dict[str, Any], page_number: int) -> int | None:
    page_info = _pick_requested_page(info, page_number) or {}
    raw_cid = page_info.get("cid") or page_info.get("id")
    try:
        return int(raw_cid) if raw_cid is not None else None
    except Exception:
        return None


async def extract_subtitles(
    bvid: str,
    info: dict[str, Any],
    page_number: int = 1,
) -> tuple[list[TranscriptSegmentOut] | None, dict[str, Any]]:
    """Attempt to extract subtitles, preferring Bilibili's own player APIs."""
    logger.info("extracting_subtitles", bvid=bvid, page_number=page_number)

    cid = _extract_cid(info, page_number)
    official_tracks = await _fetch_official_subtitle_tracks(bvid, cid)
    preferred_track = _pick_preferred_track(official_tracks)
    if preferred_track:
        segments = _download_subtitle_track(preferred_track["subtitle_url"])
        if segments:
            subtitle_source = "subtitle-ai" if preferred_track.get("is_ai") else "subtitle-official"
            metadata = {
                "subtitle_source": subtitle_source,
                "subtitle_language": preferred_track.get("lang") or None,
                "subtitle_track_count": len(official_tracks),
                "official_subtitle_available": True,
            }
            logger.info(
                "official_subtitles_found",
                bvid=bvid,
                subtitle_source=subtitle_source,
                language=metadata["subtitle_language"],
                track_count=len(official_tracks),
                segment_count=len(segments),
            )
            return segments, metadata

    segments, metadata = _parse_yt_dlp_subtitles(info)
    if segments:
        logger.info("subtitles_found_in_metadata", bvid=bvid, count=len(segments))
        return segments, metadata

    url = f"https://www.bilibili.com/video/{bvid}"
    opts = _build_yt_dlp_opts(page_number)
    opts.update(
        {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": list(TRACK_LANGUAGE_PREFERENCE),
            "subtitlesformat": "json3/json/vtt/srt",
        }
    )

    def _try_subs():
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except Exception:
                return None

    info_with_subs = await asyncio.to_thread(_try_subs)
    if info_with_subs:
        segments, metadata = _parse_yt_dlp_subtitles(info_with_subs)
        if segments:
            logger.info("subtitles_found_via_write_subs", bvid=bvid, count=len(segments))
            return segments, metadata

    logger.info("no_subtitles_available", bvid=bvid)
    return None, {
        "subtitle_source": None,
        "subtitle_language": None,
        "subtitle_track_count": 0,
        "official_subtitle_available": False,
    }


async def extract(url: str) -> ExtractResult:
    """Full extraction pipeline: validate URL -> metadata -> subtitles."""
    bvid = validate_and_extract_bvid(url)
    page_number = extract_page_number(url)

    if bvid == "__SHORT_LINK__":
        bvid = await resolve_short_link(url)

    info = await extract_metadata(bvid, page_number)
    subtitles, subtitle_metadata = await extract_subtitles(bvid, info, page_number)

    pages = info.get("entries") or info.get("pages") or []
    page_count = len(pages) if pages else 1
    page_info = _pick_requested_page(info, page_number) or info

    return ExtractResult(
        bvid=bvid,
        title=page_info.get("title") or info.get("title", "Unknown Title"),
        author=info.get("uploader", info.get("channel", "Unknown Author")),
        thumbnail_url=page_info.get("thumbnail") or info.get("thumbnail", ""),
        duration_seconds=int(page_info.get("duration") or info.get("duration") or 0),
        view_count=int(info.get("view_count", 0)),
        publish_date=info.get("upload_date", ""),
        description=page_info.get("description") or info.get("description", ""),
        page_count=page_count,
        subtitles=subtitles,
        has_subtitles=subtitles is not None and len(subtitles) > 0,
        subtitle_source=subtitle_metadata["subtitle_source"],
        subtitle_language=subtitle_metadata["subtitle_language"],
        subtitle_track_count=subtitle_metadata["subtitle_track_count"],
        official_subtitle_available=subtitle_metadata["official_subtitle_available"],
    )
