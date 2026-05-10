import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "BiliBookLLM - Transcript Workspace",
  description:
    "Process Bilibili videos into usable transcripts with official captions first and local ASR as fallback.",
  keywords: ["Bilibili", "Transcript", "Subtitles", "ASR", "Whisper", "Notes"],
  authors: [{ name: "BiliBookLLM Team" }],
  openGraph: {
    title: "BiliBookLLM - Transcript Workspace",
    description:
      "Process Bilibili videos into usable transcripts with official captions first and local ASR as fallback.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
