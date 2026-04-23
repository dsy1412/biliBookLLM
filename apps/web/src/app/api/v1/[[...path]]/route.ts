import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

const hopByHop = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

function buildTarget(pathParts: string[], search: string) {
  const sub = pathParts.length > 0 ? pathParts.join("/") : "";
  return sub ? `${backend}/api/v1/${sub}${search}` : `${backend}/api/v1${search || ""}`;
}

async function proxy(request: NextRequest, pathParts: string[]) {
  const target = buildTarget(pathParts, request.nextUrl.search);
  const headers = new Headers();
  request.headers.forEach((v, k) => {
    if (!hopByHop.has(k.toLowerCase())) {
      headers.set(k, v);
    }
  });
  // 要求后端不压缩，避免 undici 自动解压后仍带 Content-Encoding/错误的 Content-Length，导致转发体损坏或 500
  headers.set("accept-encoding", "identity");

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "follow",
  };
  if (hasBody) {
    init.body = await request.arrayBuffer();
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120_000);
    const r = await fetch(target, { ...init, signal: controller.signal });
    clearTimeout(timeout);

    // 与上面 body 的 arrayBuffer 一致：已解压的明文，不能保留 gzip 相关头
    const stripResponse = new Set([
      "content-encoding",
      "content-length",
      "transfer-encoding",
    ]);
    const outHeaders = new Headers();
    r.headers.forEach((v, k) => {
      const key = k.toLowerCase();
      if (hopByHop.has(key) || stripResponse.has(key)) {
        return;
      }
      outHeaders.set(k, v);
    });
    if (!outHeaders.has("content-type") && r.status === 200) {
      outHeaders.set("content-type", "application/json; charset=utf-8");
    }

    // 缓冲整段再返回
    const body = r.status === 204 || r.status === 205 || r.status === 304 ? null : await r.arrayBuffer();
    if (body && body.byteLength > 0) {
      outHeaders.set("content-length", String(body.byteLength));
    }
    return new NextResponse(body, { status: r.status, statusText: r.statusText, headers: outHeaders });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      {
        detail: {
          error: {
            code: "PROXY_FETCH_FAILED",
            message: `无法连接后端 ${backend}：${msg}`,
          },
        },
      },
      { status: 502 }
    );
  }
}

type Ctx = { params: Promise<{ path?: string[] }> };

export async function GET(request: NextRequest, ctx: Ctx) {
  const { path: pathParts = [] } = await ctx.params;
  return proxy(request, pathParts);
}
export async function POST(request: NextRequest, ctx: Ctx) {
  const { path: pathParts = [] } = await ctx.params;
  return proxy(request, pathParts);
}
export async function DELETE(request: NextRequest, ctx: Ctx) {
  const { path: pathParts = [] } = await ctx.params;
  return proxy(request, pathParts);
}
export async function PUT(request: NextRequest, ctx: Ctx) {
  const { path: pathParts = [] } = await ctx.params;
  return proxy(request, pathParts);
}
export async function PATCH(request: NextRequest, ctx: Ctx) {
  const { path: pathParts = [] } = await ctx.params;
  return proxy(request, pathParts);
}
export async function HEAD(request: NextRequest, ctx: Ctx) {
  const { path: pathParts = [] } = await ctx.params;
  return proxy(request, pathParts);
}
