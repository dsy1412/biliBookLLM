import UrlInput from "@/components/url-input";
import { BookOpen, Zap, Sparkles, Shield } from "lucide-react";

export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50 flex flex-col items-center pt-24 px-4 sm:px-6 lg:px-8 font-sans transition-colors duration-300">
      
      {/* Hero Section */}
      <div className="w-full max-w-4xl flex flex-col items-center text-center space-y-8 mb-16">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-sm font-medium mb-4">
          <Sparkles className="w-4 h-4" />
          <span>BiliBookLLM — AI Video Notes</span>
        </div>
        
        <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-blue-400 dark:to-indigo-400 pb-2">
          Turn Bilibili Videos <br className="hidden md:block"/> into Structured Notes
        </h1>
        
        <p className="text-lg md:text-xl text-zinc-600 dark:text-zinc-400 max-w-2xl leading-relaxed">
          Paste any Bilibili URL to instantly generate full transcripts, chapter summaries, key takeaways, and interactive Q&A.
        </p>

        {/* Input Component */}
        <div className="w-full mt-8">
          <UrlInput />
        </div>
      </div>

      {/* Features Section */}
      <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-3 gap-8 mt-16 pb-24">
        
        <div className="flex flex-col items-center text-center p-6 bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-100 dark:border-zinc-800">
          <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-xl flex items-center justify-center mb-4">
            <Zap className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold mb-2">Fast & Smart</h3>
          <p className="text-zinc-600 dark:text-zinc-400 text-sm leading-relaxed">
            Extracts native CC subtitles when available, or falls back to local AI transcription using faster-whisper.
          </p>
        </div>

        <div className="flex flex-col items-center text-center p-6 bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-100 dark:border-zinc-800">
          <div className="w-12 h-12 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-xl flex items-center justify-center mb-4">
            <BookOpen className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold mb-2">Structured Notes</h3>
          <p className="text-zinc-600 dark:text-zinc-400 text-sm leading-relaxed">
            Generates cohesive chapter summaries, key takeaways, and keyword lists to help you digest long videos.
          </p>
        </div>

        <div className="flex flex-col items-center text-center p-6 bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-100 dark:border-zinc-800">
          <div className="w-12 h-12 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 rounded-xl flex items-center justify-center mb-4">
            <Shield className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold mb-2">Privacy First</h3>
          <p className="text-zinc-600 dark:text-zinc-400 text-sm leading-relaxed">
            Local ASR fallback ensures your data stays private. Export notes to Markdown, TXT, or JSON effortlessly.
          </p>
        </div>

      </div>

    </main>
  );
}
