import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";

export const metadata: Metadata = {
  title: "VLM Reliability Layer",
  description: "A model-agnostic verification and reliability-scoring layer for vision-language models.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning><body><Providers>{children}</Providers></body></html>;
}
