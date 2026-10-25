import type { NextConfig } from "next";

const api = process.env.VLM_API_URL ?? "http://127.0.0.1:8010";

const nextConfig: NextConfig = {
  // The adapter accepts images up to 15 MB, but JSON/base64 adds ~33% overhead.
  // Next's proxy body buffer defaults to 10 MB, which truncates larger uploads.
  experimental: {
    proxyClientMaxBodySize: "32mb",
  },
  // Pin Turbopack root to the frontend directory to silence the multi-lockfile
  // warning it otherwise emits due to the workspace root's package-lock.json.
  turbopack: {
    root: import.meta.dirname,
  },
  // Lightweight endpoints are still proxied through rewrites.  The heavy
  // /api/analyze endpoint is handled by a route handler in
  // app/api/analyze/route.ts with an explicit 5-minute timeout instead.
  async rewrites() {
    return [
      { source: "/api/config", destination: `${api}/api/config` },
      { source: "/api/evaluation", destination: `${api}/api/evaluation` },
      { source: "/api/benchmarks", destination: `${api}/api/benchmarks` },
      { source: "/api/review", destination: `${api}/api/review` },
      { source: "/api/history", destination: `${api}/api/history` },
      { source: "/api/history/:id", destination: `${api}/api/history/:id` },
      { source: "/health", destination: `${api}/health` },
    ];
  },
};

export default nextConfig;
