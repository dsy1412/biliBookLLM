# BiliBookLLM

[English](./README.md)

BiliBookLLM 是一个 **本地优先** 的 B 站视频转录工具。  
它的重点不是把网站上线，而是让你在自己电脑上方便、稳定地拿到视频字幕。

当前结构保持不变：

- `apps/web`：Next.js 前端
- `apps/api`：FastAPI 后端
- `desktop/`：Electron 桌面启动器

这个项目现在的核心原则是：

**能直接拿 B 站官方字幕 / AI 字幕，就不要先下载音频做本地 ASR。**

> 仓库：<https://github.com/dsy1412/biliBookLLM.git>

## 现在主要能做什么

- 粘贴一个或多个 B 站链接
- 优先探测视频是否已经有官方字幕或 AI 字幕
- 如果有字幕，直接拉取字幕 JSON
- 如果没有字幕，再回退到本地 Whisper ASR
- 在本地任务面板里查看处理状态
- 通过 Electron 当作桌面软件使用

## 字幕获取逻辑

这个项目现在明确是 **字幕优先**，不是“先下载音频再识别”。

当前优先级：

1. `x/web-interface/view?bvid=...`
2. `x/player/wbi/v2?bvid=...&cid=...`
3. `x/player/v2?bvid=...&cid=...`
4. yt-dlp 自带的字幕元数据兜底
5. 本地下载音频 + Whisper ASR

也就是说，只要视频已经暴露出字幕轨道，就会优先直接拿字幕 JSON，再转换成 transcript segments。

这样做的好处：

- 不必每次都下载音频
- 更省磁盘空间
- 官方字幕 / AI 字幕通常比本地识别更准
- 对已有字幕的视频，速度更快

相关实现文件：

- [apps/api/app/modules/extractor.py](G:\vibe_codeing\biliBookLLM\apps\api\app\modules\extractor.py)
- [apps/api/app/services/pipeline.py](G:\vibe_codeing\biliBookLLM\apps\api\app\services\pipeline.py)

## 本地桌面使用

这个项目现在推荐按“本地软件”方式使用。

### 首次准备

需要先有：

- Python 3.11+
- Node.js 20+
- 如果要走 ASR 兜底，`ffmpeg` 最好在 `PATH` 里

首次执行一次：

```powershell
cd G:\vibe_codeing\biliBookLLM
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-desktop.ps1
```

这个脚本会：

- 创建 `apps/api/.venv`
- 安装后端依赖
- 安装前端依赖
- 安装 Electron 依赖
- 构建前端

### 启动方式

以后直接双击：

- [launch-desktop.bat](G:\vibe_codeing\biliBookLLM\launch-desktop.bat)

或者命令行启动：

```powershell
cd G:\vibe_codeing\biliBookLLM
npm run desktop
```

### 桌面快捷方式

可以运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create-desktop-shortcut.ps1
```

会在桌面生成：

- `C:\Users\Dsy\Desktop\BiliBookLLM.lnk`

## 手动开发模式

如果你暂时不想走 Electron，也可以手动开前后端。

### 后端

```powershell
cd apps\api
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### 前端

```powershell
cd apps\web
npm install
npm run dev
```

默认本地地址：

- 前端：`http://localhost:3000`
- 后端：`http://127.0.0.1:8001`

## 关键本地配置

前端代理逻辑：

- [apps/web/src/app/api/v1/[[...path]]/route.ts](<G:\vibe_codeing\biliBookLLM\apps\web\src\app\api\v1\[[...path]]\route.ts>)

前端示例环境变量：

- [apps/web/.env.example](G:\vibe_codeing\biliBookLLM\apps\web\.env.example)

后端环境变量：

- [apps/api/.env](G:\vibe_codeing\biliBookLLM\apps\api\.env)

本地默认应保持：

```env
BACKEND_URL=http://127.0.0.1:8001
```

## 为什么日志一直刷

桌面版首页会定期轮询 `/api/v1/jobs`，让 Recent Jobs 面板自动刷新。

如果你看到后端日志持续输出，一般是因为：

- 前端正在刷新任务列表
- 后端 `DEBUG=true`，SQLAlchemy 会把查询打印出来

如果想安静一点，把 [apps/api/.env](G:\vibe_codeing\biliBookLLM\apps\api\.env) 里的：

```env
DEBUG=true
```

改成：

```env
DEBUG=false
```

然后重启桌面程序。

## 主要接口

| 路径 | 方法 | 用途 |
| --- | --- | --- |
| `/api/v1/jobs` | `POST` | 提交单个视频 |
| `/api/v1/jobs/batch` | `POST` | 批量提交多个视频 |
| `/api/v1/jobs` | `GET` | 查看最近任务 |
| `/api/v1/jobs/{job_id}` | `GET` | 查看任务状态 |
| `/api/v1/jobs/{job_id}/result` | `GET` | 获取已完成转录结果 |
| `/api/v1/jobs/{job_id}` | `DELETE` | 删除任务 |
| `/api/v1/export/{job_id}/{format}` | `GET` | 导出结果 |
| `/health` | `GET` | 健康检查 |

## 说明

- 仓库里仍然保留了一些早期 summary 相关代码，但当前真实使用路径是“先拿字幕，再决定是否需要 ASR”。
- 如果未来 B 站修改字幕接口返回结构或访问限制，这部分探测逻辑可能需要维护。

## License

MIT
