"use client";

import { useState } from "react";
import { 
  LayoutDashboard, 
  ListOrdered, 
  CheckCircle2, 
  Tag, 
  HelpCircle,
  Download
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api-client";

interface Chapter {
  title: string;
  summary: string;
  start: number;
}

interface QAPair {
  question: string;
  answer: string;
}

interface SummaryData {
  overall: string;
  chapters: Chapter[];
  key_takeaways: string[];
  keywords: string[];
  qa: QAPair[] | null;
}

interface SummaryPanelProps {
  jobId: string;
  summary: SummaryData;
}

type TabType = "overall" | "chapters" | "takeaways" | "keywords" | "qa";

export default function SummaryPanel({ jobId, summary }: SummaryPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>("overall");

  const tabs = [
    { id: "overall", label: "Summary", icon: LayoutDashboard },
    { id: "chapters", label: "Chapters", icon: ListOrdered },
    { id: "takeaways", label: "Takeaways", icon: CheckCircle2 },
    { id: "keywords", label: "Keywords", icon: Tag },
    ...(summary.qa ? [{ id: "qa", label: "Q&A", icon: HelpCircle }] : []),
  ];

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-100 dark:border-zinc-800 flex flex-col h-full overflow-hidden">
      {/* Header with Export */}
      <div className="p-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between">
        <h3 className="text-lg font-bold">AI Notes</h3>
        <div className="flex gap-2">
          {["md", "txt", "json"].map((format) => (
            <a
              key={format}
              href={`${API_BASE_URL}/export/${jobId}/${format}`}
              download
              className="px-2.5 py-1.5 text-xs font-bold uppercase tracking-wider bg-zinc-50 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-all flex items-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              {format}
            </a>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex p-1 bg-zinc-50 dark:bg-zinc-950/50 m-4 rounded-xl border border-zinc-200/50 dark:border-zinc-800/50">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as TabType)}
            className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all ${
              activeTab === tab.id
                ? "bg-white dark:bg-zinc-800 text-blue-600 dark:text-blue-400 shadow-sm"
                : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            <tab.icon className="w-4 h-4" />
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-grow overflow-y-auto p-6 pt-2 scrollbar-thin">
        {activeTab === "overall" && (
          <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h4 className="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-4">Executive Summary</h4>
            <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed text-lg italic">
              "{summary.overall}"
            </p>
          </div>
        )}

        {activeTab === "chapters" && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h4 className="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-4">Video Chapters</h4>
            {summary.chapters.map((ch, idx) => (
              <div key={idx} className="relative pl-6 border-l-2 border-blue-500/20 dark:border-blue-500/10">
                <div className="absolute left-[-5px] top-1 w-2 h-2 rounded-full bg-blue-500" />
                <h5 className="font-bold text-zinc-900 dark:text-white mb-2 flex items-center gap-3">
                  {ch.title}
                  <span className="text-[10px] font-mono font-bold bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded">
                    {formatTime(ch.start)}
                  </span>
                </h5>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
                  {ch.summary}
                </p>
              </div>
            ))}
          </div>
        )}

        {activeTab === "takeaways" && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h4 className="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-4">Key Takeaways</h4>
            {summary.key_takeaways.map((item, idx) => (
              <div key={idx} className="flex gap-4 p-4 bg-zinc-50 dark:bg-zinc-950/50 rounded-xl border border-zinc-100 dark:border-zinc-800/50">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed">
                  {item}
                </p>
              </div>
            ))}
          </div>
        )}

        {activeTab === "keywords" && (
          <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h4 className="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-4">Main Topics</h4>
            <div className="flex flex-wrap gap-2">
              {summary.keywords.map((kw, idx) => (
                <span key={idx} className="px-3 py-1.5 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 rounded-full text-sm font-medium border border-indigo-100/50 dark:border-indigo-800/50">
                  #{kw}
                </span>
              ))}
            </div>
          </div>
        )}

        {activeTab === "qa" && summary.qa && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h4 className="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-4">Questions & Answers</h4>
            {summary.qa.map((item, idx) => (
              <div key={idx} className="space-y-3">
                <div className="flex gap-3">
                  <div className="w-6 h-6 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0 font-bold text-xs">Q</div>
                  <h5 className="font-bold text-zinc-900 dark:text-white">{item.question}</h5>
                </div>
                <div className="flex gap-3 pl-9">
                  <p className="text-zinc-600 dark:text-zinc-400 text-sm leading-relaxed">{item.answer}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
