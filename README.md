# BiliBookLLM

**English** · [简体中文](./README.zh.md)

Turn Bilibili videos into structured notes — a single-machine full-stack project. A FastAPI backend handles subtitle extraction / Whisper transcription / LLM summarization; a Next.js frontend submits jobs, tracks progress, reads results, and exports to Markdown / TXT / JSON.

> Repo: <https://github.com/dsy1412/biliBookLLM.git>

## Why I built this (Motivation)

I maintain my personal knowledge base in **Obsidian**. Many Bilibili creators I follow produce long-form content (science, engineering, finance), and re-watching a 20-minute video just to refresh a memory is expensive. I want to **lift the content out of the video and into my vault as searchable, linkable Markdown**, so it can be connected with my other notes via backlinks.

That led to two concrete requirements:

1. **Subtitles first.** The top priority is to reliably obtain a transcript for any Bilibili URL I paste — preferring the creator's own CC, falling back to Whisper ASR when none exists. This is the single most valuable artifact for a knowledge base: it can be read, quoted, and cross-linked.
2. **LLM summarization as a second pass.** With the transcript in hand, an LLM condenses it into chapters, key takeaways, keywords, and optional Q&A, all exported as a single Markdown file that drops cleanly into `Obsidian/Vault/Inbox/`.

**Roadmap toward a "hosted API" flavor.** The current app runs locally and calls a user-supplied LLM key. I'm planning a later variant that exposes a public REST API (and probably an Obsidian plugin / shortcut) so the whole pipeline can be triggered without a local install — paste a URL, get back a ready-to-import Markdown note. The internal contracts under `apps/api/app/routers/*` are already designed with that future in mind: stateless job IDs, JSON results, dedicated `/export` endpoint.

If you have a similar use case (Obsidian / Logseq / any plain-Markdown vault), this repo should be immediately useful.

## Architecture at a glance

```text
┌──────────────────────┐          ┌───────────────────────────────┐
│  Next.js 16 (Web)    │  /api/v1 │  FastAPI (API, uvicorn)       │
│  apps/web  :3000     ├─────────►│  apps/api  :8001 (default)    │
│  Route Handler proxy │          │  yt-dlp / faster-whisper / LLM│
└──────────────────────┘          └───────────────────────────────┘
                                               │
                                               ▼
                                     SQLite (data/bilibookllm.db)
```

The browser only talks to the same-origin `/api/v1/*`; `apps/web/src/app/api/v1/[[...path]]/route.ts` proxies to the backend (`BACKEND_URL`). This avoids CORS and `Failed to fetch`.

## Repository layout

```text
apps/
  api/                 FastAPI service
    app/
      main.py          App entry + CORS + exception handlers
      config.py        Pydantic settings (.env)
      db/              SQLAlchemy engine & base
      models/          Job / Transcript / SummaryResult
      schemas/         Pydantic response models
      routers/
        jobs.py        /api/v1/jobs (including /result)
        export.py      /api/v1/export/{job_id}/{format}
      modules/
        extractor.py   yt-dlp + BV-ID validation
        transcriber.py faster-whisper
        summarizer.py  chunked LLM summarization
        exporter.py    Markdown / TXT / JSON export
      services/pipeline.py   Job pipeline
    scripts/dev_smoke.py     End-to-end smoke script (uses a fixed BV URL)
    pyproject.toml
  web/                 Next.js 16 (Turbopack) + React 19 + Tailwind 4
    src/
      app/
        page.tsx                Home (submit a job)
        jobs/[id]/page.tsx      Reader
        api/v1/[[...path]]/route.ts   Same-origin proxy to FastAPI
      lib/api-client.ts         Typed client
      components/               UI components
    package.json
```

## Quick start

### 1) Backend (Python ≥ 3.11)

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -e .[dev]
copy .env.example .env         # set LLM_API_KEY, etc.
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Important: the default port is **8001**. On Windows, `uvicorn --reload` can leak zombie listening sockets on 8000 when Ctrl-C'd hard, which then serves stale 500s (plain text `Internal Server Error`). 8001 avoids that. If you need 8000, verify it is truly free first (`netstat -ano | findstr :8000`).

### 2) Frontend (Node ≥ 20)

```bash
cd apps/web
npm install
copy .env.example .env         # empty default is fine
npm run dev                    # http://localhost:3000
```

`apps/web/.env`:

```env
# Leave NEXT_PUBLIC_API_URL unset → browser only hits same-origin /api/v1,
# which route.ts proxies to BACKEND_URL below.
BACKEND_URL=http://127.0.0.1:8001
# NEXT_PUBLIC_API_URL=http://127.0.0.1:8001/api/v1
```

### 3) One-command smoke test (recommended)

The repo ships an end-to-end smoke script that uses a fixed Bilibili URL (`BV1TRdbBeETz`):

```bash
cd apps/web
npm run smoke:api
```

It will:

1. Validate that `BV1TRdbBeETz` parses through `extractor.validate_and_extract_bvid`.
2. Hit `API_BASE` (default `http://127.0.0.1:8001`) for `/health` and, if a completed job exists, `GET /api/v1/jobs/{id}/result`.
3. Unless `SKIP_NEXT=1` is set, repeat the request through `NEXT_BASE` (default `http://127.0.0.1:3000`) to assert the Next proxy returns the same 200 body.

Override via environment:

```powershell
$env:API_BASE="http://127.0.0.1:8001"
$env:NEXT_BASE="http://127.0.0.1:3000"
$env:SKIP_NEXT="1"    # only test the backend directly
```

## Main endpoints

| Path                                 | Method | Description                                                                   |
| ------------------------------------ | ------ | ----------------------------------------------------------------------------- |
| `/api/v1/jobs`                       | POST   | Submit a Bilibili URL, create a new job (202)                                 |
| `/api/v1/jobs`                       | GET    | Paginated list, optional `status` filter                                      |
| `/api/v1/jobs/{job_id}`              | GET    | Current status and progress                                                   |
| `/api/v1/jobs/{job_id}/result`       | GET    | Full result of a completed job (UTF-8 JSON; `/result` must register before `/{job_id}`) |
| `/api/v1/jobs/{job_id}`              | DELETE | Delete a job                                                                  |
| `/api/v1/export/{job_id}/{format}`   | GET    | Export as `markdown` / `txt` / `json`                                         |
| `/health`                            | GET    | Health check                                                                  |

## Proxy implementation notes (`apps/web/.../route.ts`)

- Force `Accept-Encoding: identity` when calling the backend, to prevent Node's undici from transparently decompressing the body while still forwarding the upstream `Content-Encoding: gzip` / wrong `Content-Length` to the browser.
- Buffer the response, strip `content-encoding` / `content-length` / `transfer-encoding`, and rewrite `content-length` from the buffered bytes.
- End-to-end timeout is 120s; failures respond with 502 JSON (`detail.error.code / message`), which `api-client.ts`'s `throwIfNotOk` renders into readable messages.

## Troubleshooting

- **`Internal Server Error (HTTP 500)`** with a plain-text body: most likely a stale backend process, or a schema that still requires `str` for fields like `llm_model`. Ensure `apps/api/app/schemas/job.py` has `ProcessingInfo.llm_model: str | None = None`, then restart the backend.
- **`Failed to fetch`**: the browser tried to hit the API directly. Keep `NEXT_PUBLIC_API_URL` unset so it only talks to same-origin `/api/v1`.
- **`GET /{job_id}/result` → 404/405/empty**: make sure `@router.get("/{job_id}/result")` is defined *before* `@router.get("/{job_id}")` in FastAPI, otherwise the catch-all wins route matching.

## License

MIT. PRs welcome.
