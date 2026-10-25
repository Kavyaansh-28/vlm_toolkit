"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 20_000, retry: 1 } } }));
  return <QueryClientProvider client={client}><ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}><>{children}<Toaster theme="dark" position="bottom-right" richColors /></></ThemeProvider></QueryClientProvider>;
}
