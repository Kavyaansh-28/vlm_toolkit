export type Claim = {
  id: string; type: string; subject: string; value?: string | number | null;
  attribute?: string | null; object?: string | null; text?: string;
  instance_id?: string | null; surface?: string | null;
};

export type Evidence = {
  claim_id: string; status: "SUPPORTED" | "CONTRADICTED" | "UNSUPPORTED" | "AMBIGUOUS" | string;
  score: number; source: string[]; confidence: number; boxes: number[][];
  verified_value?: string | number | null; explanation: string;
  evidence_quality?: number | null; signals: Record<string, unknown>;
  diagnosis?: string | null; binding_status?: string | null; instance_ids: string[];
  region_crop?: string | null;
};

export type ClaimGraph = {
  nodes: { id: string; label: string; kind?: string }[];
  edges: { source: string; target: string; label?: string; claim_id?: string }[];
  claims: { id: string; type: string; subject: string; attribute?: string | null; value?: string | number | null; object?: string | null }[];
};

export type ClaimAction = "ACCEPT" | "CORRECT" | "ABSTAIN";

export type Candidate = {
  id: string; text: string; model: string; claims: Claim[]; evidence: Evidence[];
  agreement: number; agreement_available?: boolean; reliability: number;
  decision: "ACCEPT" | "CORRECT" | "RERANK" | "ABSTAIN" | string; decision_reason?: string;
  corrected_text: string; diagnosis: string[]; probability?: number | null;
  probability_available?: boolean; claim_reliability: Record<string, number>; graph: ClaimGraph;
  claim_actions?: Record<string, ClaimAction | string>; claim_values?: Record<string, number>;
  action_details?: Record<string, string>; selected?: boolean; num_tokens?: number | null;
  original_response?: string; generator_provider?: string; verifier_provider?: string; verifier_model?: string;
  latency_ms?: number | null; generation_strategy?: string; stage_latency_ms?: Record<string, number>;
};

export type AnalysisPayload = { query: string; image_id?: string; experiment_id?: number; candidates: Candidate[] };
export type HistorySummary = { id: number; created_at: string; query: string };
export type HistoryItem = HistorySummary & { payload: AnalysisPayload };
export type AppConfig = {
  providers: string[]; models: { id: string; model: string }[]; provider: string;
  defaults: {
    candidate_count: number; verification_weight: number; agreement_weight: number; probability_weight?: number;
    high_threshold: number; low_threshold: number; rerank_threshold?: number; tuned?: boolean;
    thresholds?: Record<string, { lo: number; hi: number }>;
  };
};
export type Evaluation = { available: boolean; message?: string; calibration_available?: boolean; sample_count?: number };

export type PopeMetrics = { status: string; sample_count: number; accuracy: number; precision: number; recall: number; f1: number; yes_ratio: number; abstention_rate: number; corrected_yes_to_no?: number };
export type ChairMetrics = { status: string; sample_count: number; CHAIR_S: number; CHAIR_I: number; object_recall: number; avg_length: number };
export type Latency = { available: boolean; ratio?: number | null; mean_base_ms?: number; mean_total_ms?: number; measured_on?: string };
export type BenchmarkReport = {
  status?: string; message?: string; timestamp?: string;
  results?: {
    pope: Record<string, Record<string, PopeMetrics>>; chair: Record<string, ChairMetrics>;
    latency: Record<string, Latency>; calibration: Record<string, { available: boolean; ece?: number | null; brier?: number; sample_count?: number }>;
    meta?: { model?: string; precision?: string; hardware?: string; tuned?: boolean; thresholds?: Record<string, number[]> };
  };
};

export type ReviewItem = {
  experiment_id: number; created_at: string; query: string; candidate_id: string; claim_id: string;
  claim: Claim; claim_text: string; sentence: string; v?: number | null; status?: string | null;
  explanation: string; region_crop?: string | null; label?: string | null; note?: string;
};
