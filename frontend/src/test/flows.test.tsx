import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Workspace from "../pages/Workspace";
import History from "../pages/History";
import Models from "../pages/Models";
import { mockApi, renderWithApp } from "./utils";
import { BANK, RUN, SCENARIOS } from "./fixtures";

const base = {
  "GET /api/v1/banks": [BANK],
  "GET /api/v1/products": [{ id: "p1", bank_id: "b1", code: "card", name: "Карта", category: "credit_card", description: "", is_demo: true }],
  "GET /api/v1/scenarios": SCENARIOS,
  "GET /api/v1/providers": { live_available: false, default_provider: "auto", routing_policy: "policy", providers: [
    { name: "yandex", label: "YandexGPT", model: null, configured: false, missing_config: ["YANDEX_API_KEY"], quality_tier: 2, cost_per_1k_tokens: null, supports_json: true, tasks: [], circuit_open: false, latency_ema_ms: null, calls: 0, failures: 0, last_error: null, status: "not_configured" }] },
  "GET /api/v1/settings": { bank: { bank_id: "b1", default_mode: "demo", default_provider: "auto", default_tone: "neutral", quality_preference: "balanced", allow_documents_to_llm: false, retention_days: 90 }, platform: { tones: {}, max_upload_mb: 10, allowed_formats: [] } },
  "GET /api/v1/history": { items: [], total: 0, limit: 5, offset: 0 },
};

describe("Workspace user flow", () => {
  it("runs a demo scenario and polls real state until completed", async () => {
    let polls = 0;
    const { calls } = mockApi({
      ...base,
      "POST /api/v1/process": { ...RUN, execution_status: "running", result_status: null, final_answer: null, stages: RUN.stages.map((s) => ({ ...s, status: "pending" })) },
      "GET /api/v1/process/r1": () => (++polls < 2 ? { ...RUN, execution_status: "running", result_status: null } : RUN),
    });
    renderWithApp(<Workspace />);
    const option = await screen.findByRole("option", { name: /Ошибка в процентной ставке/ });
    await userEvent.click(option);
    expect(screen.getByRole("radio", { name: /Live AI/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Запустить проверку" }));
    expect(await screen.findByTestId("final-answer", {}, { timeout: 4000 })).toHaveTextContent("29,9%");
    const post = calls.find((c) => c.key === "POST /api/v1/process");
    expect(post?.body).toMatchObject({ mode: "demo", scenario_id: "rate-error", bank_id: "b1" });
    expect(polls).toBeGreaterThanOrEqual(2);
  });

  it("shows API error message when processing is refused", async () => {
    mockApi({ ...base, "POST /api/v1/process": new Response(JSON.stringify({ error: { code: "DEMO_NEEDS_ANSWER", message: "В Demo Mode генерация моделью не выполняется." } }), { status: 422 }) });
    renderWithApp(<Workspace />);
    await userEvent.click(await screen.findByRole("option", { name: /Безопасный ответ/ }));
    await userEvent.click(screen.getByRole("button", { name: "Запустить проверку" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("В Demo Mode генерация моделью не выполняется.");
  });

  it("own-answer mode requires an answer before running", async () => {
    mockApi(base);
    renderWithApp(<Workspace />);
    await screen.findByRole("option", { name: /Безопасный ответ/ });
    await userEvent.click(screen.getByRole("radio", { name: "Проверить свой ответ AI" }));
    const btn = screen.getByRole("button", { name: "Запустить проверку" });
    await userEvent.clear(screen.getByLabelText("Вопрос клиента"));
    await userEvent.type(screen.getByLabelText("Вопрос клиента"), "Какая ставка?");
    expect(btn).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Ответ AI для проверки"), "Ставка 25% годовых");
    expect(btn).toBeEnabled();
  });
});

describe("History", () => {
  it("empty state", async () => {
    mockApi(base);
    renderWithApp(<History />);
    expect(await screen.findByText("История пуста")).toBeInTheDocument();
  });
  it("renders stored runs", async () => {
    mockApi({ ...base, "GET /api/v1/history": { items: [RUN], total: 1, limit: 15, offset: 0 } });
    renderWithApp(<History />);
    expect(await screen.findByText("Какая ставка?")).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("READY");
  });
  it("error state when API is down", async () => {
    mockApi({ ...base, "GET /api/v1/history": new Response("{}", { status: 500 }) });
    renderWithApp(<History />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});

describe("Models", () => {
  it("shows honest not-configured status and demo hint", async () => {
    mockApi(base);
    renderWithApp(<Models />);
    expect(await screen.findByText("Не настроен")).toBeInTheDocument();
    expect(screen.getByText(/доступен только/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Проверить доступность/ })).toBeDisabled();
  });
});
