"""开发环境烟雾测试：固定 B 站 URL 的 BVID 校验 + 直连 API 的 /result + 可选经 Next 反代。

用法（在 apps/api 下）: .venv/Scripts/python scripts/dev_smoke.py
环境: API_BASE（默认 http://127.0.0.1:8000）、NEXT_BASE（默认 http://127.0.0.1:3000）、SKIP_NEXT=1 跳过经 Next 的断言。
"""
from __future__ import annotations

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)
os.chdir(_API_ROOT)

import httpx

# 与用户在 UI 中使用的长链接一致
SAMPLE = (
    "https://www.bilibili.com/video/BV1TRdbBeETz/"
    "?spm_id_from=333.1007.tianma.2-1-3.click&vd_source=27ce5a85d3cc5b0a1d555b55e9d26bc1"
)


def main() -> int:
    from app.modules.extractor import validate_and_extract_bvid

    bvid = validate_and_extract_bvid(SAMPLE)
    assert bvid == "BV1TRdbBeETz", f"unexpected bvid: {bvid!r}"
    print("bvid ok:", bvid)

    base = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
    # 与代理侧一致，避免对 gzip/length 的歧义
    req_headers = {"Accept-Encoding": "identity"}

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=req_headers) as c:
        r = c.get(f"{base}/health")
        r.raise_for_status()
        print("api health ok")

        r = c.get(f"{base}/api/v1/jobs", params={"limit": 10, "status": "completed"})
        r.raise_for_status()
        data = r.json()
        jobs = data.get("jobs", [])
        if not jobs:
            print("无 completed 任务，跳过 /result 与 Next 反代")
            return 0
        job_id = jobs[0]["job_id"]

        r = c.get(f"{base}/api/v1/jobs/{job_id}/result")
        print("result (direct):", r.status_code, "bytes", len(r.content))
        if r.status_code == 500 and (r.text or "").strip() == "Internal Server Error":
            print(
                "提示: 对账 TestClient/新端口正常而 8000 为 500 时，说明 8000 上不是当前代码的进程，"
                "请重启 API（如: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000，工作目录 apps/api）后再测。",
            )
        r.raise_for_status()
        j = r.json()
        assert j.get("job_id") == job_id, j
        print("result json ok, job_id:", job_id)

    if os.environ.get("SKIP_NEXT", "") == "1":
        print("SKIP_NEXT=1，跳过经 Next 的测试")
        return 0

    next_base = os.environ.get("NEXT_BASE", "http://127.0.0.1:3000").rstrip("/")
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True, headers=req_headers) as c:
            r = c.get(f"{next_base}/api/v1/jobs/{job_id}/result")
    except httpx.ConnectError as e:
        print("Next 未启动或不可达，跳过反代测试:", e)
        return 0
    print("result (via next):", r.status_code, "bytes", len(r.content))
    if r.status_code != 200:
        print("body (truncated):", (r.text or "")[:800])
    r.raise_for_status()
    j2 = r.json()
    assert j2.get("job_id") == job_id, j2
    print("next 反代 /result 200 ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
