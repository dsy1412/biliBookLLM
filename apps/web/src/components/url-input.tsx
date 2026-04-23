"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createJob } from "@/lib/api-client";
import { Loader2, ArrowRight } from "lucide-react";

// B 站常出现 .../BVxxxxxxxxx/?spm=...（BV 与 ? 之间多一个 /），原正则只接受 BV 后直接接 ? 会误拒
const BILIBILI_URL_PATTERN =
  /^(https?:\/\/(?:www\.)?bilibili\.com\/video\/BV[a-zA-Z0-9]{10}\/?|https?:\/\/b23\.tv\/[a-zA-Z0-9]+)(\?.*)?$/;

export default function UrlInput() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setError("Please enter a Bilibili URL");
      return;
    }

    if (!BILIBILI_URL_PATTERN.test(trimmedUrl)) {
      setError("Invalid Bilibili URL. Please use bilibili.com/video/BV... or b23.tv/...");
      return;
    }

    setLoading(true);
    try {
      const data = await createJob(trimmedUrl);
      if (data && data.job_id) {
        router.push(`/jobs/${data.job_id}`);
      } else {
        throw new Error("Job ID not returned from server");
      }
    } catch (err: any) {
      setError(err.message || "Something went wrong. Make sure the backend is running.");
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto flex flex-col gap-2">
      <div className="relative flex items-center w-full">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste Bilibili URL here..."
          className="w-full pl-6 pr-16 py-4 rounded-full border border-zinc-200 bg-white/50 backdrop-blur-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all dark:bg-zinc-900/50 dark:border-zinc-800 dark:text-white text-lg"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading}
          className="absolute right-2 p-3 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center"
        >
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ArrowRight className="w-5 h-5" />}
        </button>
      </div>
      {error && <p className="text-red-500 text-sm pl-4">{error}</p>}
    </form>
  );
}
