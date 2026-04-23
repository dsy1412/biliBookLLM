import { Clock, Eye, Calendar, Layers } from "lucide-react";

interface VideoMetadata {
  title: string;
  author: string;
  thumbnail_url: string;
  duration_seconds: number;
  view_count: number;
  publish_date: string;
  bvid: string;
  page_count: number;
}

export default function VideoCard({ metadata }: { metadata: VideoMetadata }) {
  const formatDuration = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const formatNumber = (num: number) => {
    if (num >= 10000) return `${(num / 10000).toFixed(1)}W`;
    return num.toString();
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr || dateStr.length !== 8) return dateStr;
    // yt-dlp returns upload_date as YYYYMMDD
    return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
  };

  return (
    <div className="flex flex-col md:flex-row gap-6 p-4 md:p-6 bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-100 dark:border-zinc-800">
      <div className="relative w-full md:w-64 flex-shrink-0 aspect-video rounded-xl overflow-hidden bg-zinc-100 dark:bg-zinc-800">
        {metadata.thumbnail_url ? (
          <img
            src={metadata.thumbnail_url}
            alt={metadata.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-400">
            No Thumbnail
          </div>
        )}
        <div className="absolute bottom-2 right-2 px-2 py-1 bg-black/70 text-white text-xs font-medium rounded">
          {formatDuration(metadata.duration_seconds)}
        </div>
      </div>

      <div className="flex flex-col justify-center flex-grow">
        <h2 className="text-xl font-bold line-clamp-2 mb-2 leading-snug">
          <a
            href={`https://www.bilibili.com/video/${metadata.bvid}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            {metadata.title}
          </a>
        </h2>
        
        <p className="text-zinc-600 dark:text-zinc-400 font-medium mb-4">
          UP: {metadata.author}
        </p>

        <div className="flex flex-wrap gap-4 text-sm text-zinc-500 dark:text-zinc-500">
          <div className="flex items-center gap-1.5">
            <Eye className="w-4 h-4" />
            <span>{formatNumber(metadata.view_count)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Calendar className="w-4 h-4" />
            <span>{formatDate(metadata.publish_date)}</span>
          </div>
          {metadata.page_count > 1 && (
            <div className="flex items-center gap-1.5">
              <Layers className="w-4 h-4" />
              <span>{metadata.page_count} Parts</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
