/**
 * When unset, use same-origin `/api/v1` so the browser only talks to the Next app.
 * Set NEXT_PUBLIC_API_URL in production only when the frontend should call a
 * separately deployed API host directly.
 */
const fromEnv = process.env.NEXT_PUBLIC_API_URL?.trim();
export const API_BASE_URL =
  fromEnv && fromEnv.length > 0 ? fromEnv.replace(/\/$/, "") : "/api/v1";

type FastApiDetail =
  | string
  | { error?: { message?: string }; message?: string }
  | Array<{ msg?: string }>;

export type JobStatus =
  | "pending"
  | "extracting"
  | "downloading_audio"
  | "transcribing"
  | "completed"
  | "failed"
  | "invalid";

export type TranscriptSource =
  | "subtitle-ai"
  | "subtitle-official"
  | "subtitle-ydlp"
  | "asr"
  | string
  | null;

export interface JobOptions {
  force_asr?: boolean;
  whisper_model?: string;
  generate_qa?: boolean;
  llm_model?: string | null;
}

export interface CreateJobResponse {
  job_id: string;
  status: JobStatus;
  created_at: string;
  url: string;
  reused_existing?: boolean;
}

export interface BatchJobItem {
  url: string;
  job_id?: string | null;
  status: JobStatus;
  created_at?: string | null;
  reused_existing?: boolean;
  error?: { code: string; message: string } | null;
}

export interface BatchCreateResponse {
  items: BatchJobItem[];
}

export interface JobListItem {
  job_id: string;
  status: JobStatus;
  bvid: string;
  url: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
  progress: number;
  stage?: string | null;
  transcript_source?: TranscriptSource;
  error?: { code: string; message: string } | null;
}

export interface JobListResponse {
  total: number;
  jobs: JobListItem[];
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  stage?: string | null;
  created_at: string;
  updated_at: string;
  metadata?: {
    title: string;
    author: string;
    thumbnail_url: string;
    duration_seconds: number;
    view_count: number;
    publish_date: string;
    bvid: string;
    page_count: number;
  } | null;
  transcript_source?: TranscriptSource;
  error?: { code: string; message: string } | null;
}

function messageFromApiBody(body: { detail?: FastApiDetail }): string | null {
  const detail = body.detail;
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  if (!Array.isArray(detail) && typeof detail === "object" && detail.error?.message) {
    return detail.error.message;
  }
  if (typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
    return detail.message;
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
      const message = messageFromApiBody(parsed);
      if (message) throw new Error(message);
    } catch (error) {
      if (!(error instanceof SyntaxError)) {
        throw error;
      }
    }
  }

  throw new Error(
    trimmed
      ? `${trimmed.length > 500 ? `${trimmed.slice(0, 500)}...` : trimmed} (HTTP ${status})`
      : `${fallback} (HTTP ${status})`
  );
}

async function getJson<T>(input: RequestInfo, init: RequestInit, fallback: string): Promise<T> {
  const response = await fetch(input, init);
  await throwIfNotOk(response, fallback);
  return response.json() as Promise<T>;
}

export function createJob(url: string, options?: JobOptions) {
  return getJson<CreateJobResponse>(
    `${API_BASE_URL}/jobs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, options: options || {} }),
    },
    "Failed to create job"
  );
}

export function createJobsBatch(urls: string[], options?: JobOptions) {
  return getJson<BatchCreateResponse>(
    `${API_BASE_URL}/jobs/batch`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls, options: options || {} }),
    },
    "Failed to create jobs"
  );
}

export function listJobs(params?: { limit?: number; offset?: number; status?: string }) {
  const url = new URL(`${API_BASE_URL}/jobs`, typeof window === "undefined" ? "http://localhost" : window.location.origin);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (params?.offset) url.searchParams.set("offset", String(params.offset));
  if (params?.status) url.searchParams.set("status", params.status);

  const target = url.pathname + url.search;
  return getJson<JobListResponse>(target, { method: "GET" }, "Failed to list jobs");
}

export function getJobStatus(jobId: string) {
  return getJson<JobStatusResponse>(
    `${API_BASE_URL}/jobs/${jobId}`,
    { method: "GET" },
    "Failed to fetch job status"
  );
}

export function getJobResult(jobId: string) {
  return getJson<any>(
    `${API_BASE_URL}/jobs/${jobId}/result`,
    { method: "GET" },
    "Failed to fetch job result"
  );
}
