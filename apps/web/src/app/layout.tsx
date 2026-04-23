import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "BiliBookLLM — AI-Powered Bilibili Video Notes",
  description: "Transform Bilibili videos into structured notes instantly. Get transcripts, summaries, key takeaways, and interactive Q&A powered by AI.",
  keywords: ["Bilibili", "AI", "Notes", "Transcription", "Whisper", "LLM", "NotebookLLM"],
  authors: [{ name: "BiliBookLLM Team" }],
  openGraph: {
    title: "BiliBookLLM — AI-Powered Bilibili Video Notes",
    description: "Transform Bilibili videos into structured notes instantly.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
