"""Transcriber module — audio download and ASR via faster-whisper."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import structlog

from app.config import settings
from app.schemas.job import TranscriptSegmentOut
from app.schemas.pipeline import TranscribeResult

logger = structlog.get_logger(__name__)

# Module-level model cache — load once, reuse
_whisper_model = None
_whisper_model_name = None


class TranscriptionError(Exception):
    """Raised when transcription fails."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _get_whisper_model(model_name: str | None = None):
    """Get or load the faster-whisper model (singleton)."""
    global _whisper_model, _whisper_model_name

    target_model = model_name or settings.whisper_model

    if _whisper_model is not None and _whisper_model_name == target_model:
        return _whisper_model

    try:
        from faster_whisper import WhisperModel

        logger.info("loading_whisper_model", model=target_model, device=settings.whisper_device)

        _whisper_model = WhisperModel(
            target_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        _whisper_model_name = target_model

        logger.info("whisper_model_loaded", model=target_model)
        return _whisper_model

    except Exception as e:
        raise TranscriptionError(
            "ASR_LOAD_FAILED",
            f"Failed to load Whisper model '{target_model}': {e}",
        )


async def download_audio(bvid: str) -> Path:
    """Download the best audio stream for a Bilibili video using yt-dlp.

    Returns the path to the downloaded audio file.
    """
    import yt_dlp

    url = f"https://www.bilibili.com/video/{bvid}"
    temp_dir = settings.temp_path
    output_template = str(temp_dir / f"{bvid}_audio.%(ext)s")

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [],  # No post-processing — we'll use ffmpeg ourselves
    }

    # Add cookie auth
    if settings.bilibili_cookies_file:
        opts["cookiefile"] = settings.bilibili_cookies_file
    elif settings.bilibili_sessdata:
        opts["http_headers"] = {"Cookie": f"SESSDATA={settings.bilibili_sessdata}"}

    logger.info("downloading_audio", bvid=bvid)

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                # Find the downloaded file
                if info and "requested_downloads" in info:
                    return Path(info["requested_downloads"][0]["filepath"])
                # Fallback: search temp dir for the file
                for f in temp_dir.glob(f"{bvid}_audio.*"):
                    return f
                raise TranscriptionError(
                    "DOWNLOAD_FAILED", f"Audio file not found after download for {bvid}"
                )
            except yt_dlp.utils.DownloadError as e:
                raise TranscriptionError("DOWNLOAD_FAILED", f"Failed to download audio: {e}")

    audio_path = await asyncio.to_thread(_download)
    logger.info("audio_downloaded", bvid=bvid, path=str(audio_path))
    return audio_path


async def convert_to_wav(audio_path: Path) -> Path:
    """Convert audio to 16kHz mono WAV using ffmpeg.

    This is the optimal format for Whisper inference.
    """
    wav_path = audio_path.with_suffix(".wav")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-ar", "16000",      # 16kHz sample rate
        "-ac", "1",           # Mono channel
        "-c:a", "pcm_s16le",  # 16-bit PCM
        str(wav_path),
    ]

    logger.info("converting_audio", input=str(audio_path), output=str(wav_path))

    def _convert():
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
            )
            if result.returncode != 0:
                raise TranscriptionError(
                    "CONVERSION_FAILED",
                    f"ffmpeg conversion failed: {result.stderr[:500]}",
                )
        except FileNotFoundError:
            raise TranscriptionError(
                "FFMPEG_NOT_FOUND",
                "ffmpeg is not installed or not on system PATH",
            )
        except subprocess.TimeoutExpired:
            raise TranscriptionError(
                "CONVERSION_TIMEOUT",
                "ffmpeg conversion timed out (> 5 minutes)",
            )

    await asyncio.to_thread(_convert)

    if not wav_path.exists():
        raise TranscriptionError("CONVERSION_FAILED", "WAV file was not created")

    logger.info("audio_converted", wav_path=str(wav_path))
    return wav_path


async def transcribe_audio(
    wav_path: Path,
    model_name: str | None = None,
    progress_callback: Any = None,
) -> list[TranscriptSegmentOut]:
    """Transcribe a WAV file using faster-whisper.

    Args:
        wav_path: Path to the 16kHz mono WAV file
        model_name: Whisper model name override
        progress_callback: Optional callable(segment_index, total_estimate)

    Returns:
        List of timestamped transcript segments
    """
    logger.info("starting_transcription", wav_path=str(wav_path), model=model_name)

    def _transcribe():
        model = _get_whisper_model(model_name)

        segments_iter, info = model.transcribe(
            str(wav_path),
            language="zh",
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 500,
            },
            beam_size=5,
            word_timestamps=False,
        )

        logger.info(
            "transcription_info",
            language=info.language,
            language_probability=f"{info.language_probability:.2f}",
            duration=f"{info.duration:.1f}s",
        )

        result = []
        for i, segment in enumerate(segments_iter):
            result.append(
                TranscriptSegmentOut(
                    start=round(segment.start, 2),
                    end=round(segment.end, 2),
                    text=segment.text.strip(),
                )
            )
            if progress_callback and i % 10 == 0:
                try:
                    progress_callback(i, None)
                except Exception:
                    pass

        return result

    segments = await asyncio.to_thread(_transcribe)
    logger.info("transcription_complete", segment_count=len(segments))
    return segments


def cleanup_temp_files(*paths: Path):
    """Remove temporary audio files."""
    for path in paths:
        try:
            if path.exists():
                path.unlink()
                logger.debug("cleaned_temp_file", path=str(path))
        except OSError as e:
            logger.warning("cleanup_failed", path=str(path), error=str(e))


async def transcribe(bvid: str, model_name: str | None = None) -> TranscribeResult:
    """Full transcription pipeline: download audio → convert → ASR.

    This is the main entry point for the transcriber module.
    """
    audio_path = None
    wav_path = None

    try:
        # Step 1: Download audio
        audio_path = await download_audio(bvid)

        # Step 2: Convert to WAV
        wav_path = await convert_to_wav(audio_path)

        # Step 3: Transcribe
        used_model = model_name or settings.whisper_model
        segments = await transcribe_audio(wav_path, model_name)

        if not segments:
            raise TranscriptionError(
                "ASR_EMPTY", "Transcription produced no segments — audio may be silent"
            )

        return TranscribeResult(
            source="asr",
            language="zh-CN",
            segments=segments,
            whisper_model=used_model,
        )

    finally:
        # Cleanup temp files
        paths_to_clean = [p for p in (audio_path, wav_path) if p is not None]
        cleanup_temp_files(*paths_to_clean)
