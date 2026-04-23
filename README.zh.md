# BiliBookLLM

[English](./README.md) · **简体中文**

把 B 站视频变成结构化笔记的单机全栈项目：FastAPI 后端负责抓取字幕 / Whisper 转写 / LLM 摘要，Next.js 前端负责提交任务、查看进度与阅读结果，支持导出 Markdown / TXT / JSON。

> 仓库：<https://github.com/dsy1412/biliBookLLM.git>

## 写这个的动机

我用 **Obsidian** 维护个人知识库。我关注的一些 B 站 UP 主产出的是长内容（科普、工程、金融），每次想回忆某个点又要把 20 分钟视频重看一遍，成本太高。我的核心诉求是：**把视频里的内容"搬"进 Obsidian，变成可检索、可双链的 Markdown**，让它与我的其他笔记融合。

这就引出两个具体目标：

1. **优先拿到字幕文件。** 任何一条 B 站链接粘进来，我都希望稳定拿到一份转写：优先使用 UP 主自带的 CC 字幕；没有的话用 Whisper 做 ASR 兜底。对知识库而言，字幕本身就是最值钱的产物——可读、可引用、可被其他笔记反向链接。
2. **LLM 摘要作为第二段加工。** 拿到字幕后交给 LLM，产出章节、要点、关键词和可选的问答对，最后打包成单个 Markdown 文件，能直接丢进 `Obsidian/Vault/Inbox/`。

**后续规划：做一个"API 版本"。** 目前是单机运行、用户自己填 LLM Key。之后会出一个对外暴露公共 REST API（大概率还带一个 Obsidian 插件或快捷方式）的版本——粘贴 URL、直接返回可入库的 Markdown，不需要本地安装 Python 环境。`apps/api/app/routers/*` 里已经按这个目标设计了接口：无状态 job id、JSON 结果、独立的 `/export` 端点。

如果你的使用场景类似（Obsidian / Logseq / 任何纯 Markdown 知识库），这个仓库应当立刻可用。

## 架构一览

```text
┌──────────────────────┐          ┌───────────────────────────────┐
│  Next.js 16 (Web)    │  /api/v1 │  FastAPI (API, uvicorn)       │
│  apps/web  :3000     ├─────────►│  apps/api  :8001 (默认)       │
│  Route Handler 反代  │          │  yt-dlp / faster-whisper / LLM│
└──────────────────────┘          └───────────────────────────────┘
                                               │
                                               ▼
                                     SQLite (data/bilibookllm.db)
```

前端在浏览器只请求同域 `/api/v1/*`，由 `apps/web/src/app/api/v1/[[...path]]/route.ts` 反代到后端（`BACKEND_URL`），避免 CORS / `Failed to fetch`。

## 目录结构

```text
apps/
  api/                 FastAPI 服务
    app/
      main.py          应用入口 + CORS + 异常处理
      config.py        Pydantic settings (.env)
      db/              SQLAlchemy 引擎 & 基类
      models/          Job / Transcript / SummaryResult
      schemas/         Pydantic 响应模型
      routers/
        jobs.py        /api/v1/jobs （含 /result）
        export.py      /api/v1/export/{job_id}/{format}
      modules/
        extractor.py   yt-dlp + BV 号校验
        transcriber.py faster-whisper
        summarizer.py  LLM 分块摘要
        exporter.py    Markdown / TXT / JSON 导出
      services/pipeline.py   任务流水线
    scripts/dev_smoke.py     端到端冒烟脚本（含固定 BV 链接）
    pyproject.toml
  web/                 Next.js 16 (Turbopack) + React 19 + Tailwind 4
    src/
      app/
        page.tsx                首页（提交任务）
        jobs/[id]/page.tsx      阅读页
        api/v1/[[...path]]/route.ts   同域反代到 FastAPI
      lib/api-client.ts         前端封装
      components/               UI 组件
    package.json
```

## 快速开始

### 1) 后端（Python ≥ 3.11）

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -e .[dev]
copy .env.example .env         # 填 LLM_API_KEY 等
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

重要：默认端口是 **8001**。Windows 上 `uvicorn --reload` 有概率在被硬杀时留下僵尸监听 socket，占住 8000，前端会收到 `Internal Server Error (HTTP 500)` 的纯文本（旧代码）。切到 8001 是最稳妥的规避方式；如果你要换回 8000，先确认端口真正空闲（`netstat -ano | findstr :8000`）。

### 2) 前端（Node ≥ 20）

```bash
cd apps/web
npm install
copy .env.example .env         # 默认空即可
npm run dev                    # http://localhost:3000
```

`apps/web/.env`：

```env
# 不设置 NEXT_PUBLIC_API_URL → 浏览器只走同域 /api/v1，由 route.ts 反代到 BACKEND_URL
BACKEND_URL=http://127.0.0.1:8001
# NEXT_PUBLIC_API_URL=http://127.0.0.1:8001/api/v1
```

### 3) 一键冒烟测试（推荐）

项目内置了用固定 B 站链接 `https://www.bilibili.com/video/BV1TRdbBeETz/...` 做端到端验证的脚本：

```bash
cd apps/web
npm run smoke:api
```

该脚本会：

1. 校验 `BV1TRdbBeETz` 能被 `extractor.validate_and_extract_bvid` 正确解析。
2. 用 `API_BASE`（默认 `http://127.0.0.1:8001`）调 `/health`，以及 `GET /api/v1/jobs/{id}/result`。
3. 若未设 `SKIP_NEXT=1`，再经 `NEXT_BASE`（默认 `http://127.0.0.1:3000`）的 Next 反代请求同一接口，断言 200。

环境变量可通过 shell 覆盖：

```powershell
$env:API_BASE="http://127.0.0.1:8001"
$env:NEXT_BASE="http://127.0.0.1:3000"
$env:SKIP_NEXT="1"    # 仅想测直连后端
```

## 主要接口

| 路径                                | 方法   | 说明                                                                       |
| ----------------------------------- | ------ | -------------------------------------------------------------------------- |
| `/api/v1/jobs`                      | POST   | 提交 B 站 URL，创建新 job（202）                                           |
| `/api/v1/jobs`                      | GET    | 分页列出 jobs，可按 `status` 过滤                                          |
| `/api/v1/jobs/{job_id}`             | GET    | 当前状态与进度                                                             |
| `/api/v1/jobs/{job_id}/result`      | GET    | 已完成任务的完整结果（UTF-8 JSON；`/result` 必须先于 `/{job_id}` 注册）     |
| `/api/v1/jobs/{job_id}`             | DELETE | 删除任务                                                                   |
| `/api/v1/export/{job_id}/{format}`  | GET    | 导出 `markdown` / `txt` / `json`                                           |
| `/health`                           | GET    | 健康检查                                                                   |

## 反代注意事项（`apps/web/.../route.ts`）

- 向后端请求时强制 `Accept-Encoding: identity`，避免 Node 的 undici 自动解压却仍把 `Content-Encoding: gzip`、错误的 `Content-Length` 转发给浏览器。
- 响应缓冲后再返回，并删除 `content-encoding` / `content-length` / `transfer-encoding`，重写 `content-length`。
- 整条链路超时 120s，失败返回 502 JSON（含 `detail.error.code / message`），`api-client.ts` 的 `throwIfNotOk` 能据此显示人类可读的错误文案。

## 排查常见问题

- **`Internal Server Error (HTTP 500)`** 且响应体是纯文本：大概率是旧代码进程没被杀，或 schema 对 `llm_model` 之类字段还要求 `str`。确认 `apps/api/app/schemas/job.py` 里 `ProcessingInfo.llm_model: str | None = None`，重启后端即可。
- **`Failed to fetch`**：浏览器直连了 API。保持 `NEXT_PUBLIC_API_URL` 为空，让浏览器只走同域 `/api/v1`。
- **`GET /{job_id}/result` 返回 404/405/空**：确保 FastAPI 中 `@router.get("/{job_id}/result")` 定义在 `@router.get("/{job_id}")` 之前；否则更具体的路由会被泛化路由抢匹配。

## 许可

MIT。欢迎 PR。
