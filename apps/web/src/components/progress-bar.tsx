import { Loader2, CheckCircle2, XCircle, AlertCircle } from "lucide-react";

interface ProgressBarProps {
  status: string;
  progress: number;
  stage?: string | null;
  error?: string | null;
}

export default function ProgressBar({ status, progress, stage, error }: ProgressBarProps) {
  const isFailed = status === "failed";
  const isCompleted = status === "completed";

  let statusText = "Initializing...";
  if (status === "extracting") statusText = "Extracting video metadata...";
  if (status === "downloading_audio") statusText = "Downloading audio for transcription...";
  if (status === "transcribing") statusText = "Transcribing audio (local AI)...";
  if (status === "chunking") statusText = "Segmenting transcript...";
  if (status === "summarizing") statusText = "Generating AI summaries...";
  if (isCompleted) statusText = "Processing complete!";
  if (isFailed) statusText = "Processing failed";

  // Override with specific stage if available
  if (stage && !isCompleted && !isFailed) {
    statusText = stage;
  }

  return (
    <div className="w-full bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm border border-zinc-100 dark:border-zinc-800">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {isFailed ? (
            <XCircle className="w-5 h-5 text-red-500" />
          ) : isCompleted ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          ) : (
            <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
          )}
          <span className="font-medium text-zinc-900 dark:text-zinc-100">
            {statusText}
          </span>
        </div>
        <span className="text-sm font-semibold text-zinc-500 dark:text-zinc-400">
          {progress}%
        </span>
      </div>

      <div className="w-full h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ease-out ${
            isFailed
              ? "bg-red-500"
              : isCompleted
              ? "bg-emerald-500"
              : "bg-blue-500"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/50 rounded-lg flex gap-3 text-red-700 dark:text-red-400">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}
    </div>
  );
}
