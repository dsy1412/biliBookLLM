/**
 * When unset, use same-origin `/api/v1` so the browser only talks to the Next app;
 * `next.config` rewrites proxy to FastAPI (see BACKEND_URL). Set NEXT_PUBLIC_API_URL
 * in production to call a separate API host directly.
 */
const fromEnv = process.env.NEXT_PUBLIC_API_URL?.trim();
export const API_BASE_URL =
  fromEnv && fromEnv.length > 0 ? fromEnv.replace(/\/$/, "") : "/api/v1";

type FastApiDetail = string | { error?: { message?: string }; message?: string } | Array<{ msg?: string }>;

function messageFromApiBody(body: { detail?: FastApiDetail }): string | null {
  const d = body.detail;
  if (d == null) return null;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg;
  if (typeof d === "object" && d.error?.message) return d.error.message;
  if (typeof d === "object" && "message" in d && typeof (d as { message: unknown }).message === "string") {
    return (d as { message: string }).message;
  }
  return null;
}

async function throwIfNotOk(response: Response, fallback: string) {
  if (response.ok) return;
  const status = response.status;
  const text = (await response.text().catch(() => "")) ?? "";
  const trimmed = text.trim();

  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: FastApiDetail };
      const m = messageFromApiBody(parsed);
      if (m) {
        throw new Error(m);
      }
    } catch (e) {
      if (e instanceof SyntaxError) {
        // not valid JSON; show raw text below
      } else {
        throw e;
      }
    }
  }

  throw new Error(
    trimmed
      ? `${trimmed.length > 500 ? `${trimmed.slice(0, 500)}…` : trimmed} (HTTP ${status})`
      : `${fallback} (HTTP ${status})`
  );
}

export async function createJob(url: string, options?: any) {
  const response = await fetch(`${API_BASE_URL}/jobs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url, options: options || {} }),
  });

  await throwIfNotOk(response, "Failed to create job");
  return response.json();
}

export async function getJobStatus(jobId: string) {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
  await throwIfNotOk(response, "Failed to fetch job status");
  return response.json();
}

export async function getJobResult(jobId: string) {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/result`);
  await throwIfNotOk(response, "Failed to fetch job result");
  return response.json();
}
