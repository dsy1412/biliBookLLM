"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, CopyPlus, Loader2, Rows3, TriangleAlert } from "lucide-react";

import { BatchJobItem, createJob, createJobsBatch } from "@/lib/api-client";
import SourceBadge from "@/components/source-badge";

const BILIBILI_URL_PATTERN =
  /https?:\/\/(?:www\.)?bilibili\.com\/video\/BV[a-zA-Z0-9]{10}\/?(?:\?[^\s]*)?|https?:\/\/b23\.tv\/[a-zA-Z0-9]+|BV[a-zA-Z0-9]{10}/g;

function extractUrls(input: string) {
  const matches = input.match(BILIBILI_URL_PATTERN) || [];
  const unique = new Set<string>();

  for (const match of matches) {
    unique.add(match.trim());
  }

  return Array.from(unique);
}

function resultTone(item: BatchJobItem) {
  if (item.error || item.status === "invalid") return "border-red-200 bg-red-50/70 dark:border-red-900 dark:bg-red-950/20";
  if (item.reused_existing) return "border-amber-200 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/20";
  return "border-emerald-200 bg-emerald-50/70 dark:border-emerald-900 dark:bg-emerald-950/20";
}

export default function UrlInput() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<BatchJobItem[]>([]);
  const router = useRouter();

  const parsedUrls = useMemo(() => extractUrls(input), [input]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const urls = extractUrls(input);
    if (urls.length === 0) {
      setError("Paste at least one valid Bilibili video URL or BV number.");
      return;
    }

    setLoading(true);
    try {
      if (urls.length === 1) {
        const data = await createJob(urls[0]);
        setResults([
          {
            url: data.url,
            job_id: data.job_id,
            status: data.status,
            created_at: data.created_at,
            reused_existing: data.reused_existing,
          },
        ]);
        router.push(`/jobs/${data.job_id}`);
        return;
      }

      const batch = await createJobsBatch(urls);
      setResults(batch.items);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Queue videos</h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Paste one or many Bilibili links. We will prefer official Bilibili captions, then fall back to local ASR only when needed.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <label className="block">
          <span className="mb-2 inline-flex items-center gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
            <Rows3 className="h-4 w-4" />
            <span>One link per line</span>
          </span>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={"https://www.bilibili.com/video/BV...\nhttps://b23.tv/...\nBV1..."}
            className="min-h-[180px] w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
            disabled={loading}
          />
        </label>

        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span className="rounded-full bg-zinc-100 px-3 py-1 dark:bg-zinc-800">
              {parsedUrls.length} valid link{parsedUrls.length === 1 ? "" : "s"}
            </span>
            <span className="rounded-full bg-zinc-100 px-3 py-1 dark:bg-zinc-800">
              Multi-P links keep their `?p=` page when present
            </span>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-950 dark:hover:bg-zinc-200"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            <span>{loading ? "Submitting..." : parsedUrls.length > 1 ? "Start batch" : "Start job"}</span>
          </button>
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/20 dark:text-red-300">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {results.length > 0 && (
          <div className="space-y-3 pt-2">
            {results.map((item, index) => (
              <div
                key={`${item.url}-${index}`}
                className={`rounded-xl border px-4 py-3 ${resultTone(item)}`}
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">{item.url}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                      <span className="rounded-full border border-current/20 px-2 py-0.5">{item.status}</span>
                      {item.reused_existing && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-current/20 px-2 py-0.5">
                          <CopyPlus className="h-3 w-3" />
                          Reused existing job
                        </span>
                      )}
                      {!item.error && <SourceBadge source={null} />}
                    </div>
                    {item.error?.message && (
                      <div className="mt-2 text-sm text-red-700 dark:text-red-300">{item.error.message}</div>
                    )}
                  </div>

                  {item.job_id && (
                    <Link
                      href={`/jobs/${item.job_id}`}
                      className="inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-800"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      <span>Open job</span>
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </form>
    </section>
  );
}
