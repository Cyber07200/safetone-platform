export type Mode = "demo" | "live";
export type Tone = "neutral" | "friendly" | "concise" | "detailed";
export type ResultStatus = "READY" | "NEEDS_REVIEW" | "FAILED";
export type ClaimStatus = "CONFIRMED" | "CONTRADICTED" | "UNVERIFIED" | "OUTDATED_SOURCE" | "NEEDS_REVIEW";
export type Risk = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type Actuality = "current" | "superseded" | "expired" | "not_yet_effective" | "unverified";

export interface Health { status: string; version: string; default_mode: Mode; live_available: boolean; database: string }
export interface Bank { id: string; slug: string; name: string; is_demo: boolean }
export interface Product { id: string; bank_id: string; code: string; name: string; category: string; description: string; is_demo: boolean }
export interface Scenario {
  id: string; title: string; category: string; product_id: string | null; product_code: string;
  question: string; answer: string; expected_status: ResultStatus; demonstrates: string;
}

export interface Stage {
  key: string; title: string; status: StageStatus; method: string | null; summary: string | null;
  started_at: string | null; finished_at: string | null; duration_ms: number | null; warnings: string[];
}

export interface Evidence {
  relation: "supports" | "contradicts" | "related" | "matches_outdated";
  chunk_id: string; document_id: string; title: string; doc_type: string; version: number; section: string;
  page: number | null; quote: string; actuality: Actuality; document_date: string | null;
  effective_from: string | null; effective_to: string | null; source_url: string | null; is_demo: boolean;
  claim_value: string | null; source_value: string | null; retrieval_score: number;
}

export interface Claim {
  id: string; text: string; substantive: boolean; status: ClaimStatus; evidence_status: ClaimStatus; risk: Risk;
  explanation: string; notes: string[]; flags: string[]; topics: string[];
  values: { unit: string; value: number; raw: string }[]; conditions: { unit: string; value: number; raw: string }[];
  evidence: Evidence[]; action: string; correction: string | null; requires_review: boolean; skipped?: boolean;
}

export interface Source {
  chunk_id: string; document_id: string; title: string; doc_type: string; version: number; section: string;
  page: number | null; quote: string; actuality: Actuality; document_date: string | null; effective_from: string | null;
  effective_to: string | null; source_url: string | null; is_demo: boolean; used_for: { claim_id: string; relation: string }[];
}

export interface LegalChange {
  claim_id: string; action: string; before: string; after: string | null; reason: string; risk: Risk;
  basis: { title: string; section: string; version: number; actuality: string; relation: string }[];
}

export interface SemanticCheck {
  passed?: boolean; term_overlap?: number; note?: string; fallback?: string | null;
  checks?: { name: string; title: string; passed: boolean; detail: string }[];
  attempts?: { method: string; passed: boolean }[];
}

export interface AiCall {
  task: string; provider: string; model: string; ok: boolean; attempt: number; latency_ms: number | null;
  error_code: string | null; error: string | null; tokens: number | null; cost_estimate: number | null; selection_reason: string;
}

export interface RunSummary {
  id: string; bank_id: string; product_id: string | null; product_name: string | null; created_at: string;
  finished_at: string | null; mode: Mode; execution_status: "queued" | "running" | "completed" | "failed";
  result_status: ResultStatus | null; max_risk: Risk | null; question: string;
  answer_origin: "scenario" | "provider" | "user"; scenario_id: string | null; provider: string | null;
  model: string | null; tone: Tone; duration_ms: number | null; changes_count: number;
}

export interface RunDetail extends RunSummary {
  original_answer: string | null; legal_answer: string | null; final_answer: string | null;
  tokens_total: number | null; cost_estimate: number | null; stages: Stage[]; claims: Claim[]; sources: Source[];
  legal_changes: LegalChange[];
  linguistic: { tone?: string; tone_label?: string; method?: string; changes?: { type: string; description: string; count?: number }[]; candidate?: string | null; fallback?: string | null };
  semantic_check: SemanticCheck; ai_calls: AiCall[]; missing_data: string[]; notices: string[];
  error: { code: string; message: string; stage: string } | null;
}

export interface HistoryPage { items: RunSummary[]; total: number; limit: number; offset: number }

export interface DocumentItem {
  id: string; bank_id: string | null; product_id: string | null; product_name: string | null; document_key: string;
  version: number; title: string; doc_type: string; scope_label: string; document_date: string | null;
  effective_from: string | null; effective_to: string | null; actuality_status: string; effective_actuality: Actuality;
  actuality_note: string; source_url: string | null; is_demo: boolean; is_global: boolean; original_filename: string | null;
  mime_type: string | null; size_bytes: number; text_length: number; chunk_count: number; security_flags: string[]; uploaded_at: string;
}
export interface DocumentDetail extends DocumentItem { chunks: { id: string; ordinal: number; section: string; page: number | null; text: string; suspicious: boolean }[] }

export interface ProviderInfo {
  name: string; label: string; model: string | null; configured: boolean; missing_config: string[]; quality_tier: number;
  cost_per_1k_tokens: number | null; supports_json: boolean; tasks: string[]; circuit_open: boolean;
  latency_ema_ms: number | null; calls: number; failures: number; last_error: string | null;
  status: "not_configured" | "configured" | "ok" | "degraded" | "unavailable";
}
export interface ProvidersView { live_available: boolean; default_provider: string; routing_policy: string; providers: ProviderInfo[] }

export interface BankSettings {
  bank_id: string; default_mode: Mode; default_provider: string; default_tone: Tone;
  quality_preference: "economy" | "balanced" | "quality"; allow_documents_to_llm: boolean; retention_days: number;
}
export interface SettingsView { bank: BankSettings; platform: Record<string, unknown> & { tones: Record<Tone, string>; max_upload_mb: number; allowed_formats: string[] } }

export interface Stats {
  total_runs: number; by_status: Record<string, number>; by_mode: Record<string, number>; by_risk: Record<string, number>;
  claims_by_status: Record<string, number>; corrections: number; avg_duration_ms: number | null; documents: number;
  documents_needing_attention: number; recent: RunSummary[];
}

export interface ProcessInput {
  bank_id: string; product_id?: string | null; question: string; mode: Mode; scenario_id?: string | null;
  answer_text?: string | null; provider?: string | null; tone: Tone;
}
