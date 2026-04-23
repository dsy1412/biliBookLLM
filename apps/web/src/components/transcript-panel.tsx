"use client";

import { useState, useMemo } from "react";
import { Search, Clock, FileText, Download } from "lucide-react";
import { API_BASE_URL } from "@/lib/api-client";

interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

interface TranscriptPanelProps {
  jobId: string;
  segments: TranscriptSegment[];
  source?: string;
}

export default function TranscriptPanel({ jobId, segments, source }: TranscriptPanelProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredSegments = useMemo(() => {
    if (!searchQuery.trim()) return segments;
    const query = searchQuery.toLowerCase();
    return segments.filter((seg) => seg.text.toLowerCase().includes(query));
  }, [segments, searchQuery]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-100 dark:border-zinc-800 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-zinc-100 dark:border-zinc-800 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h3 className="text-lg font-bold flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-500" />
              <span>Transcript</span>
            </h3>
            {source && (
              <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 rounded">
                {source}
              </span>
            )}
          </div>

          <div className="flex gap-2">
            {["md", "txt", "json"].map((format) => (
              <a
                key={format}
                href={`${API_BASE_URL}/export/${jobId}/${format}`}
                download
                className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider bg-zinc-50 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-800 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-all flex items-center gap-1"
              >
                <Download className="w-3 h-3" />
                {format}
              </a>
            ))}
          </div>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search transcript..."
            className="w-full pl-10 pr-4 py-2 bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-grow overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {filteredSegments.length > 0 ? (
          filteredSegments.map((seg, idx) => (
            <div key={idx} className="flex gap-4 group">
              <span className="text-xs font-mono text-zinc-400 mt-1 flex-shrink-0 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatTime(seg.start)}
              </span>
              <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed group-hover:text-zinc-900 dark:group-hover:text-white transition-colors">
                {seg.text}
              </p>
            </div>
          ))
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-zinc-400 space-y-2 py-12">
            <Search className="w-8 h-8 opacity-20" />
            <p className="text-sm">No matches found for "{searchQuery}"</p>
          </div>
        )}
      </div>
    </div>
  );
}
