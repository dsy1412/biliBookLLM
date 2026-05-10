"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import ProgressBar from "@/components/progress-bar";
import SummaryPanel from "@/components/summary-panel";
import TranscriptPanel from "@/components/transcript-panel";
import VideoCard from "@/components/video-card";
import { getJobResult, getJobStatus, JobStatusResponse } from "@/lib/api-client";

function networkErrorMessage(err: unknown, fallback: string): string {
  const message = err instanceof Error ? err.message : String(err);
  const isNetwork =
    message === "Failed to fetch" ||
    (err instanceof TypeError && message.includes("fetch")) ||
    message.includes("Load failed");
  if (isNetwork) {
    return "Unable to reach the backend. Check the deployed API URL and the frontend BACKEND_URL setting.";
  }
  return message || fallback;
}

function statusTone(status: string) {
  if (status === "completed") {
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";
  }
  if (status === "failed") {
    return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
  }
  return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400";
}

export default function JobReaderPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [statusData, setStatusData] = useState<JobStatusResponse | null>(null);
  const [resultData, setResultData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let pollInterval: NodeJS.Timeout;

    const fetchResult = async () => {
      try {
        const data = await getJobResult(jobId);
        setResultData(data);
      } catch (err: unknown) {
        console.error(err);
        setError(networkErrorMessage(err, "Failed to fetch job result"));
      }
    };

    const fetchStatus = async () => {
      try {
        const data = await getJobStatus(jobId);
        setStatusData(data);

        if (data.status === "completed") {
          clearInterval(pollInterval);
          fetchResult();
        } else if (data.status === "failed") {
          clearInterval(pollInterval);
        }
      } catch (err: unknown) {
        console.error(err);
        setError(networkErrorMessage(err, "Failed to fetch job status"));
        clearInterval(pollInterval);
      }
    };

    fetchStatus();
    pollInterval = setInterval(fetchStatus, 3000);
    return () => clearInterval(pollInterval);
  }, [jobId]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 p-8 dark:bg-zinc-950">
        <div className="max-w-lg rounded-2xl border border-red-100 bg-white p-8 text-center shadow-sm dark:border-red-900/50 dark:bg-zinc-900">
          <h2 className="mb-4 text-2xl font-bold text-red-600 dark:text-red-400">Error</h2>
          <p className="mb-8 text-zinc-600 dark:text-zinc-400">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="rounded-lg bg-zinc-900 px-6 py-2 font-medium text-white transition-opacity hover:opacity-90 dark:bg-white dark:text-zinc-900"
          >
            Go Back Home
          </button>
        </div>
      </div>
    );
  }

  if (!statusData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="flex animate-pulse flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
          <p className="text-zinc-500">Loading job data...</p>
        </div>
      </div>
    );
  }

  const isProcessing = statusData.status !== "completed" && statusData.status !== "failed";

  return (
    <main className="min-h-screen bg-zinc-50 pb-24 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="flex items-center gap-2 text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
          >
            <ArrowLeft className="h-5 w-5" />
            <span className="font-medium">Back to Home</span>
          </Link>
          <span className={`rounded-full px-2.5 py-1 text-sm font-medium ${statusTone(statusData.status)}`}>
            {statusData.status.toUpperCase()}
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-8 px-4 pt-8 sm:px-6 lg:px-8">
        {statusData.metadata && (
          <VideoCard metadata={statusData.metadata} source={statusData.transcript_source} />
        )}

        {(isProcessing || statusData.status === "failed") && (
          <ProgressBar
            status={statusData.status}
            progress={statusData.progress}
            stage={statusData.stage}
            error={statusData.error?.message}
          />
        )}

        {statusData.status === "completed" && resultData && (
          <div className={`mt-8 ${resultData.summary?.overall ? "grid grid-cols-1 gap-8 lg:grid-cols-2" : "block"}`}>
            <div className="h-[800px]">
              <TranscriptPanel
                jobId={jobId}
                segments={resultData.transcript?.segments || []}
                source={resultData.processing_info?.transcript_source}
              />
            </div>

            {resultData.summary?.overall && (
              <div className="h-[800px]">
                <SummaryPanel jobId={jobId} summary={resultData.summary} />
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
