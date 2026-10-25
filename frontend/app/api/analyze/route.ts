/**
 * Next.js API route for /api/analyze.
 *
 * Instead of relying on the rewrite proxy (which has a short default timeout
 * that causes ECONNRESET / "socket hang up" on long-running VLM inference),
 * this route handler forwards the request to the Python backend with an
 * explicit 10-minute timeout.  Route handlers take precedence over rewrites,
 * so this replaces the rewrite for this one heavy endpoint while all lighter
 * endpoints (config, history, evaluation) keep using the fast rewrite proxy.
 */

const API_BASE = process.env.VLM_API_URL ?? "http://127.0.0.1:8010";

export async function POST(request: Request) {
  try {
    // Stream the raw body straight through — no parsing, no size-limit surprises.
    const body = await request.arrayBuffer();

    const upstream = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      // 10 minutes: first-run model loading plus CPU-only verification of 3 candidates
      signal: AbortSignal.timeout(600_000),
    });

    const data = await upstream.text();
    return new Response(data, {
      status: upstream.status,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      },
    });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Proxy to VLM backend failed";
    const isTimeout =
      err instanceof DOMException && err.name === "TimeoutError";
    return Response.json(
      { error: isTimeout ? "Analysis timed out (10 min). Try fewer candidates or a faster provider." : message },
      { status: isTimeout ? 504 : 502 },
    );
  }
}
