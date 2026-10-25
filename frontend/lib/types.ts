export type Claim = {
  id: string; type: string; subject: string; value?: string | number | null;
  attribute?: string | null; object?: string | null; text?: string;
  instance_id?: string | null;
};

export type Evidence = {
  claim_id: string; status: "SUPPORTED" | "CONTRADICTED" | "UNSUPPORTED" | "AMBIGUOUS" | string;
  score: number; source: string[]; confidence: number; boxes: number[][];
  verified_value?: string | number | null; explanation: string;
  evidence_quality?: number | null; signals: Record<string, unknown>;
  diagnosis?: string | null; binding_status?: string | null; instance_ids: string[];
};

export type ClaimGraph = {
  nodes: { id: string; label: string; kind?: string }[];
  edges: { source: string; target: string; label?: string; claim_id?: string }[];
  claims: { id: string; type: string; subject: string; attribute?: string | null; value?: string | number | null; object?: string | null }[];
};

export type Candidate = {
  id: string; text: string; model: string; claims: Claim[]; evidence: Evidence[];
  agreement: number; reliability: number; decision: "ACCEPT" | "CORRECT" | "RERANK" | "ABSTAIN" | string;
  corrected_text: string; diagnosis: string[]; probability?: number | null;
  probability_available?: boolean; claim_reliability: Record<string, number>; graph: ClaimGraph;
  original_response?: string; generator_provider?: string; verifier_provider?: string; verifier_model?: string; latency_ms?: number | null;
};

export type AnalysisPayload = { query: string; image_id?: string; experiment_id?: number; candidates: Candidate[] };
export type HistorySummary = { id: number; created_at: string; query: string };
export type HistoryItem = HistorySummary & { payload: AnalysisPayload };
export type AppConfig = { providers: string[]; models: { id: string; model: string }[]; provider: string; defaults: { candidate_count: number; verification_weight: number; agreement_weight: number; high_threshold: number; low_threshold: number } };
export type Evaluation = { available: boolean; message?: string; calibration_available?: boolean; sample_count?: number };
