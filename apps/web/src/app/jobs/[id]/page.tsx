"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJobStatus, getJobResult } from "@/lib/api-client";
import VideoCard from "@/components/video-card";
import ProgressBar from "@/components/progress-bar";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import TranscriptPanel from "@/components/transcript-panel";
import SummaryPanel from "@/components/summary-panel";

function networkErrorMessage(
  err: unknown,
  fallback: string
): string {
  const m = err instanceof Error ? err.message : String(err);
  const isNetwork =
    m === "Failed to fetch" ||
    (err instanceof TypeError && m.includes("fetch")) ||
    m.includes("Load failed");
  if (isNetwork) {
    return "无法连接后端。请先在 apps/api 运行 uvicorn（并监听 127.0.0.1:8000），并重启 next dev 使反代配置生效。若仍失败，可检查 .env 中的 BACKEND_URL 是否与 API 实际地址一致。";
  }
  return m || fallback;
}

export default function JobReaderPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [statusData, setStatusData] = useState<any>(null);
  const [resultData, setResultData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let pollInterval: NodeJS.Timeout;

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

    const fetchResult = async () => {
      try {
        const data = await getJobResult(jobId);
        setResultData(data);
      } catch (err: unknown) {
        console.error(err);
        setError(networkErrorMessage(err, "Failed to fetch job result"));
      }
    };

    fetchStatus();
    // Poll every 3 seconds while not completed/failed
    pollInterval = setInterval(fetchStatus, 3000);

    return () => clearInterval(pollInterval);
  }, [jobId]);

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-8 flex flex-col items-center justify-center">
        <div className="bg-white dark:bg-zinc-900 p-8 rounded-2xl shadow-sm border border-red-100 dark:border-red-900/50 max-w-lg text-center">
          <h2 className="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Error</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-8">{error}</p>
          <button 
            onClick={() => router.push("/")}
            className="px-6 py-2 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 rounded-lg font-medium hover:opacity-90 transition-opacity"
          >
            Go Back Home
          </button>
        </div>
      </div>
    );
  }

  if (!statusData) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-zinc-500">Loading job data...</p>
        </div>
      </div>
    );
  }

  const isProcessing = statusData.status !== "completed" && statusData.status !== "failed";

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50 pb-24">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-md border-b border-zinc-200 dark:border-zinc-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link 
            href="/"
            className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="font-medium">Back to Home</span>
          </Link>
          <div className="flex items-center gap-3 text-sm font-medium">
            <span className={`px-2.5 py-1 rounded-full ${
              statusData.status === 'completed' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' :
              statusData.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
              'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
            }`}>
              {statusData.status.toUpperCase()}
            </span>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 space-y-8">
        {/* Video Metadata */}
        {statusData.metadata && (
          <VideoCard metadata={statusData.metadata} />
        )}

        {/* Progress Bar (Show while processing or failed) */}
        {(isProcessing || statusData.status === "failed") && (
          <ProgressBar 
            status={statusData.status} 
            progress={statusData.progress} 
            stage={statusData.stage}
            error={statusData.error?.message}
          />
        )}

        {/* Result Reader */}
        {statusData.status === "completed" && resultData && (
          <div className={`mt-8 ${resultData.summary?.overall ? "grid grid-cols-1 lg:grid-cols-2 gap-8" : "block"}`}>
            {/* Left Panel: Transcript */}
            <div className="h-[800px]">
              <TranscriptPanel 
                jobId={jobId}
                segments={resultData.transcript?.segments || []} 
                source={resultData.processing_info?.transcript_source}
              />
            </div>

            {/* Right Panel: Summaries (Only if summary exists) */}
            {resultData.summary?.overall && (
              <div className="h-[800px]">
                <SummaryPanel 
                  jobId={jobId}
                  summary={resultData.summary}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

