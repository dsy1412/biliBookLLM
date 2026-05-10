import { Bot, Captions, Mic } from "lucide-react";

function getSourceMeta(source?: string | null) {
  switch (source) {
    case "subtitle-ai":
      return {
        label: "Official AI captions",
        className: "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950/40 dark:text-violet-300 dark:border-violet-900",
        Icon: Bot,
      };
    case "subtitle-official":
      return {
        label: "Official subtitles",
        className: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900",
        Icon: Captions,
      };
    case "subtitle-ydlp":
      return {
        label: "Subtitle fallback",
        className: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900",
        Icon: Captions,
      };
    case "asr":
      return {
        label: "Local ASR",
        className: "bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-900 dark:text-zinc-300 dark:border-zinc-800",
        Icon: Mic,
      };
    default:
      return {
        label: "Pending detection",
        className: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-900",
        Icon: Captions,
      };
  }
}

export default function SourceBadge({ source }: { source?: string | null }) {
  const meta = getSourceMeta(source);
  const Icon = meta.Icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${meta.className}`}
    >
      <Icon className="h-3.5 w-3.5" />
      <span>{meta.label}</span>
    </span>
  );
}
