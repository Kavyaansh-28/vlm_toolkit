import type { AnalysisPayload, AppConfig, Evaluation, HistoryItem, HistorySummary } from "@/lib/types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers }, cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error ?? `Request failed (${response.status})`);
  return data as T;
}

export const getConfig = () => request<AppConfig>("/api/config");
export const getEvaluation = () => request<Evaluation>("/api/evaluation");
export const getHistory = () => request<HistorySummary[]>("/api/history");
export const getHistoryItem = (id: number) => request<HistoryItem>(`/api/history/${id}`);

export async function analyzeImage(input: {
  file: File; query: string; candidateCount: number; provider: string; verifierProvider: string;
  manualResponse: string; verificationWeight: number; agreementWeight: number;
  highThreshold: number; lowThreshold: number;
}): Promise<{ analysis: AnalysisPayload; experiment_id?: number; warning?: string | null }> {
  const buffer = await input.file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  return request("/api/analyze", { method: "POST", body: JSON.stringify({
    filename: input.file.name, image_base64: btoa(binary), query: input.query,
    candidate_count: input.candidateCount, provider: input.provider, verifier_provider: input.verifierProvider,
    manual_response: input.manualResponse, weights: { verification: input.verificationWeight, agreement: input.agreementWeight },
    high_threshold: input.highThreshold, low_threshold: input.lowThreshold,
  }) });
}
