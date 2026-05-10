import { Bot, Captions, FileText, Layers3 } from "lucide-react";

import JobsDashboard from "@/components/jobs-dashboard";
import UrlInput from "@/components/url-input";

const highlights = [
  {
    title: "Official captions first",
    body: "Check whether the video already exposes official Bilibili subtitles or AI captions before touching local ASR.",
    icon: Captions,
  },
  {
    title: "Batch-friendly queue",
    body: "Paste a stack of links in one go and keep an eye on which jobs are reusing existing transcripts.",
    icon: Layers3,
  },
  {
    title: "Transcript-centric",
    body: "This flow is optimized for exporting clean text and timestamps, since that is the part you actually need.",
    icon: FileText,
  },
  {
    title: "AI captions visible",
    body: "The dashboard makes it obvious when a transcript came from official AI captions versus local fallback.",
    icon: Bot,
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
        <section className="rounded-xl border border-zinc-200 bg-white px-5 py-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                <Captions className="h-4 w-4" />
                <span>BiliBookLLM transcript workspace</span>
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
                Batch-process Bilibili videos and prefer the platform&apos;s own captions when they exist
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600 dark:text-zinc-400">
                Paste links, let the app probe official subtitle availability, and only fall back to local transcription when the video truly needs it.
              </p>
            </div>
          </div>
        </section>

        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
          <div className="space-y-8">
            <UrlInput />

            <section className="grid gap-4 md:grid-cols-2">
              {highlights.map((item) => (
                <div
                  key={item.title}
                  className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
                >
                  <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{item.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{item.body}</p>
                </div>
              ))}
            </section>
          </div>

          <JobsDashboard />
        </div>
      </div>
    </main>
  );
}
