import type { RunDetail, Scenario, Stage } from "../types/api";

export const BANK = { id: "b1", slug: "demo", name: "Банк «Ясный Берег» (DEMO)", is_demo: true };
export const stages = (status: Stage["status"] = "completed"): Stage[] =>
  ["generation", "claim_extraction", "source_retrieval", "legal_verification", "legal_correction", "linguistic_rewrite", "semantic_validation", "final_response"]
    .map((key) => ({ key, title: key, status, method: key === "generation" ? "demo_scenario" : "m", summary: `summary ${key}`, started_at: null, finished_at: null, duration_ms: 3, warnings: [] }));

export const SCENARIOS: Scenario[] = [
  { id: "rate-error", title: "Ошибка в процентной ставке", category: "contradiction", product_id: "p1", product_code: "card", question: "Какая ставка?", answer: "Ставка 19,9%", expected_status: "READY", demonstrates: "demo" },
  { id: "safe-balance", title: "Безопасный ответ", category: "safe", product_id: "p1", product_code: "card", question: "Как узнать баланс?", answer: "В приложении", expected_status: "READY", demonstrates: "demo" },
];

export const RUN: RunDetail = {
  id: "r1", bank_id: "b1", product_id: "p1", product_name: "Карта", created_at: "2026-09-24T10:00:00Z", finished_at: "2026-09-24T10:00:01Z",
  mode: "demo", execution_status: "completed", result_status: "READY", max_risk: "HIGH", question: "Какая ставка?", answer_origin: "scenario",
  scenario_id: "rate-error", provider: null, model: null, tone: "neutral", duration_ms: 40, changes_count: 1,
  original_answer: "Ставка по покупкам — 19,9% годовых.", legal_answer: "Ставка по покупкам — 29,9% годовых.", final_answer: "Ставка по покупкам — 29,9% годовых.",
  tokens_total: null, cost_estimate: null, stages: stages(),
  claims: [{ id: "c1", text: "Ставка по покупкам — 19,9% годовых.", substantive: true, status: "CONTRADICTED", evidence_status: "CONTRADICTED", risk: "HIGH",
    explanation: "В ответе 19,9%, в источнике 29,9%", notes: [], flags: [], topics: ["rate"], values: [], conditions: [],
    evidence: [{ relation: "contradicts", chunk_id: "ch1", document_id: "d1", title: "Тарифы по карте", doc_type: "tariff", version: 1, section: "п. 1.1", page: null,
      quote: "Ставка по покупкам — 29,9% годовых.", actuality: "current", document_date: null, effective_from: "2026-03-01", effective_to: null, source_url: null,
      is_demo: true, claim_value: "19,9%", source_value: "29,9%", retrieval_score: 5 }],
    action: "corrected", correction: "Ставка по покупкам — 29,9% годовых.", requires_review: false }],
  sources: [{ chunk_id: "ch1", document_id: "d1", title: "Тарифы по карте", doc_type: "tariff", version: 1, section: "п. 1.1", page: null, quote: "Ставка по покупкам — 29,9% годовых.",
    actuality: "current", document_date: null, effective_from: "2026-03-01", effective_to: null, source_url: null, is_demo: true, used_for: [{ claim_id: "c1", relation: "contradicts" }] }],
  legal_changes: [{ claim_id: "c1", action: "corrected", before: "19,9%", after: "29,9%", reason: "по тарифу", risk: "HIGH", basis: [{ title: "Тарифы", section: "п. 1.1", version: 1, actuality: "current", relation: "contradicts" }] }],
  linguistic: { tone: "neutral", tone_label: "Нейтральный банковский", method: "deterministic-style-dictionary", changes: [] },
  semantic_check: { passed: true, checks: [{ name: "numbers_preserved", title: "Суммы сохранены", passed: true, detail: "ok" }] },
  ai_calls: [], missing_data: [], notices: ["DEMO MODE: исходный ответ не сгенерирован моделью"], error: null,
};

export const FAILED_RUN: RunDetail = {
  ...RUN, id: "r2", mode: "live", answer_origin: "provider", execution_status: "failed", result_status: "FAILED", final_answer: null, legal_answer: null,
  original_answer: null, claims: [], sources: [], legal_changes: [], semantic_check: {}, linguistic: {},
  stages: stages("skipped").map((s, i) => (i === 0 ? { ...s, status: "failed", summary: "Все провайдеры вернули ошибку" } : s)),
  error: { code: "ALL_PROVIDERS_FAILED", message: "Все доступные AI-провайдеры вернули ошибку", stage: "generation" }, notices: [],
  ai_calls: [{ task: "generation", provider: "gigachat", model: "GigaChat", ok: false, attempt: 1, latency_ms: null, error_code: "PROVIDER_HTTP_ERROR", error: "HTTP 503", tokens: null, cost_estimate: null, selection_reason: "auto" }],
};
