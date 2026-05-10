"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Clock3, ExternalLink, ListFilter, RefreshCw } from "lucide-react";

import { JobListItem, listJobs } from "@/lib/api-client";
import SourceBadge from "@/components/source-badge";

type FilterKey = "all" | "running" | "completed" | "failed";

function formatRelativeTime(iso: string) {
  const time = new Date(iso).getTime();
  if (Number.isNaN(time)) return iso;
  const diffMinutes = Math.max(0, Math.round((Date.now() - time) / 60000));
  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.round(diffHours / 24)}d ago`;
}

function statusTone(status: string) {
  switch (status) {
    case "completed":
      return "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900";
    case "failed":
      return "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900";
    default:
      return "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900";
  }
}

export default function JobsDashboard() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      try {
        const response = await listJobs({ limit: 18 });
        if (mounted) {
          setJobs(response.jobs);
          setLoading(false);
        }
      } catch (error) {
        console.error(error);
        if (mounted) setLoading(false);
      }
    };

    load();
    const timer = setInterval(load, 5000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const counts = useMemo(
    () => ({
      all: jobs.length,
      running: jobs.filter((job) => !["completed", "failed"].includes(job.status)).length,
      completed: jobs.filter((job) => job.status === "completed").length,
      failed: jobs.filter((job) => job.status === "failed").length,
    }),
    [jobs]
  );

  const visibleJobs = useMemo(() => {
    if (filter === "all") return jobs;
    if (filter === "running") return jobs.filter((job) => !["completed", "failed"].includes(job.status));
    return jobs.filter((job) => job.status === filter);
  }, [filter, jobs]);

  const filters: Array<{ id: FilterKey; label: string }> = [
    { id: "all", label: "All" },
    { id: "running", label: "Running" },
    { id: "completed", label: "Completed" },
    { id: "failed", label: "Failed" },
  ];

  return (
    <section className="rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
        <div>
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Recent jobs</h2>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Track which videos are using official Bilibili captions and which fall back to ASR.
          </p>
        </div>
        <RefreshCw className={`h-4 w-4 text-zinc-400 ${loading ? "animate-spin" : ""}`} />
      </div>

      <div className="flex flex-wrap gap-2 border-b border-zinc-200 px-5 py-3 dark:border-zinc-800">
        <ListFilter className="mt-2 h-4 w-4 text-zinc-400" />
        {filters.map((item) => (
          <button
            key={item.id}
            onClick={() => setFilter(item.id)}
            className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
              filter === item.id
                ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-950"
                : "border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:border-zinc-600 dark:hover:text-zinc-200"
            }`}
          >
            {item.label} ({counts[item.id]})
          </button>
        ))}
      </div>

      <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
        {visibleJobs.length === 0 && !loading && (
          <div className="px-5 py-10 text-center text-sm text-zinc-500 dark:text-zinc-400">
            No jobs yet.
          </div>
        )}

        {visibleJobs.map((job) => (
          <div key={job.job_id} className="flex flex-col gap-3 px-5 py-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(job.status)}`}>
                    {job.status}
                  </span>
                  <SourceBadge source={job.transcript_source} />
                </div>
                <div className="mt-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  {job.title || job.bvid}
                </div>
                <div className="mt-1 break-all text-xs text-zinc-500 dark:text-zinc-400">{job.url}</div>
                {job.stage && job.status !== "completed" && job.status !== "failed" && (
                  <div className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{job.stage}</div>
                )}
                {job.error?.message && (
                  <div className="mt-2 text-xs text-red-600 dark:text-red-400">{job.error.message}</div>
                )}
              </div>

              <div className="flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
                <div className="inline-flex items-center gap-1.5">
                  <Clock3 className="h-3.5 w-3.5" />
                  <span>{formatRelativeTime(job.updated_at)}</span>
                </div>
                <Link
                  href={`/jobs/${job.job_id}`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                >
                  <span>Open</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>

            <div className="h-2 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
              <div
                className={`h-full transition-all ${
                  job.status === "failed"
                    ? "bg-red-500"
                    : job.status === "completed"
                    ? "bg-emerald-500"
                    : "bg-blue-500"
                }`}
                style={{ width: `${Math.max(4, job.progress)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
