# BiliBookLLM

[简体中文](./README.zh.md)

BiliBookLLM is a local-first desktop-style tool for turning Bilibili videos into usable transcripts.

The project keeps the current architecture:

- `apps/web`: Next.js frontend
- `apps/api`: FastAPI backend
- `desktop/`: Electron launcher for one-click local use

The main goal is simple: **prefer Bilibili's own subtitle tracks whenever possible, and only fall back to local ASR when subtitles are unavailable.**

> Repo: <https://github.com/dsy1412/biliBookLLM.git>

## What it does

- Paste one or many Bilibili links
- Detect whether the video already exposes official subtitles or AI subtitles
- Fetch subtitle JSON directly when available
- Fall back to local Whisper transcription only when needed
- Track jobs in a local dashboard
- Run as a local desktop app through Electron

## Subtitle-first logic

This project is intentionally biased toward **subtitle retrieval**, not audio downloading.

Current priority:

1. `x/web-interface/view?bvid=...`
2. `x/player/wbi/v2?bvid=...&cid=...`
3. `x/player/v2?bvid=...&cid=...`
4. yt-dlp subtitle metadata fallback
5. local audio download + Whisper ASR fallback

If a subtitle track exists, the backend downloads the subtitle JSON and builds transcript segments from that data directly.

This is better than always using ASR because it:

- avoids unnecessary audio downloads
- uses less disk space
- is usually more accurate than local speech recognition
- keeps startup and processing faster for videos that already have captions

The relevant implementation lives in:

- [apps/api/app/modules/extractor.py](G:\vibe_codeing\biliBookLLM\apps\api\app\modules\extractor.py)
- [apps/api/app/services/pipeline.py](G:\vibe_codeing\biliBookLLM\apps\api\app\services\pipeline.py)

## Local desktop usage

This project is now meant to be used locally.

### First-time setup

Requirements:

- Python 3.11+
- Node.js 20+
- `ffmpeg` in `PATH` if ASR fallback is needed

Bootstrap once:

```powershell
cd G:\vibe_codeing\biliBookLLM
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-desktop.ps1
```

This script:

- creates `apps/api/.venv`
- installs backend dependencies
- installs frontend dependencies
- installs Electron dependencies
- builds the web app

### Launch

Double-click:

- [launch-desktop.bat](G:\vibe_codeing\biliBookLLM\launch-desktop.bat)

or run:

```powershell
cd G:\vibe_codeing\biliBookLLM
npm run desktop
```

A desktop shortcut can be created with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create-desktop-shortcut.ps1
```

That script creates:

- `C:\Users\Dsy\Desktop\BiliBookLLM.lnk`

## Development mode

If you want to run the services manually instead of Electron:

### Backend

```powershell
cd apps\api
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### Frontend

```powershell
cd apps\web
npm install
npm run dev
```

Default local routing:

- frontend: `http://localhost:3000`
- backend: `http://127.0.0.1:8001`

## Important local config

Frontend proxy config:

- [apps/web/src/app/api/v1/[[...path]]/route.ts](<G:\vibe_codeing\biliBookLLM\apps\web\src\app\api\v1\[[...path]]\route.ts>)

Frontend example env:

- [apps/web/.env.example](G:\vibe_codeing\biliBookLLM\apps\web\.env.example)

Backend env:

- [apps/api/.env](G:\vibe_codeing\biliBookLLM\apps\api\.env)

For normal local use, keep:

```env
BACKEND_URL=http://127.0.0.1:8001
```

## Job dashboard behavior

The desktop UI polls `/api/v1/jobs` periodically so the Recent Jobs panel stays fresh.

If you see continuous API log output, that is usually because:

- the dashboard is refreshing job state
- backend `DEBUG=true` is printing SQL logs

To reduce log noise, change this in [apps/api/.env](G:\vibe_codeing\biliBookLLM\apps\api\.env):

```env
DEBUG=false
```

## Main endpoints

| Path | Method | Purpose |
| --- | --- | --- |
| `/api/v1/jobs` | `POST` | Submit one Bilibili video |
| `/api/v1/jobs/batch` | `POST` | Submit multiple Bilibili videos |
| `/api/v1/jobs` | `GET` | List recent jobs |
| `/api/v1/jobs/{job_id}` | `GET` | Get job status |
| `/api/v1/jobs/{job_id}/result` | `GET` | Get completed transcript result |
| `/api/v1/jobs/{job_id}` | `DELETE` | Delete a job |
| `/api/v1/export/{job_id}/{format}` | `GET` | Export transcript/result |
| `/health` | `GET` | Health check |

## Notes

- This repo still contains summary-related code paths from earlier iterations, but the current local workflow is centered on transcript retrieval first.
- If Bilibili changes subtitle response formats or access rules, the official subtitle probes may need maintenance.

## License

MIT.
