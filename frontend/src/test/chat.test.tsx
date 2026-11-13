import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Chat from "../pages/Chat";
import { mockApi, renderWithApp } from "./utils";
import { BANK } from "./fixtures";

const CONV = { id: "c1", title: "Какая сумма вкладов застрахована?", message_count: 2, created_at: "2026-11-12T10:00:00Z", updated_at: "2026-11-12T10:00:00Z" };
const SOURCE = { document_id: "d1", title: "Федеральный закон № 177-ФЗ «О страховании вкладов»", section: "Статья 11", doc_type: "law", actuality: "current", source_url: "https://base.garant.ru/12133717/", quote: "Возмещение по вкладам выплачивается в размере 100 процентов суммы вкладов…" };

describe("Chat", () => {
  it("sends a message with the owner token and shows the answer with sources", async () => {
    const userMsg = { id: "m1", role: "user", content: "Какая сумма вкладов застрахована?", sources: [], mode: null, model: null, created_at: CONV.created_at };
    const botMsg = { id: "m2", role: "assistant", content: "Застрахованы вклады до **1 400 000 ₽** (177-ФЗ, ст. 11).", sources: [SOURCE], mode: "live", model: "GigaChat", created_at: CONV.created_at };
    const { calls, fn } = mockApi({
      "GET /api/v1/banks": [BANK],
      "GET /api/health": { status: "ok", version: "t", default_mode: "demo", live_available: true, database: "ok" },
      "GET /api/v1/chat/conversations": [],
      "GET /api/v1/chat/conversations/c1": { ...CONV, messages: [userMsg, botMsg] },
      "POST /api/v1/chat/messages": { conversation: CONV, user_message: userMsg, assistant_message: botMsg },
    });
    renderWithApp(<Chat />, { path: "/app/chat/:id?", route: "/app/chat" });
    expect(await screen.findByText(/Помощник банка/)).toBeInTheDocument();

    await waitFor(() => expect(screen.getByLabelText("Сообщение")).toBeEnabled());
    await userEvent.type(screen.getByLabelText("Сообщение"), "Какая сумма вкладов застрахована?{Enter}");
    expect(await screen.findByText("1 400 000 ₽")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/v1/chat/messages")?.body).toMatchObject({ bank_id: BANK.id, content: "Какая сумма вкладов застрахована?", mode: "live" });
    const [, init] = fn.mock.calls.find(([u, i]) => String(u).includes("/chat/messages") && i?.method === "POST")!;
    expect((init!.headers as Record<string, string>)["X-Chat-Owner"]).toMatch(/^[A-Za-z0-9_-]{43}$/);

    await userEvent.click(screen.getByRole("button", { name: /Источники · 1/ }));
    expect(await screen.findByText(SOURCE.title)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Сообщение")).toHaveValue(""));
  });

  it("keeps the typed text when sending fails", async () => {
    mockApi({
      "GET /api/v1/banks": [BANK],
      "GET /api/health": { status: "ok", version: "t", default_mode: "demo", live_available: false, database: "ok" },
      "GET /api/v1/chat/conversations": [],
      "POST /api/v1/chat/messages": new Response(JSON.stringify({ error: { code: "AI_PROVIDER_ERROR", message: "GigaChat недоступен" } }), { status: 502 }),
    });
    renderWithApp(<Chat />, { path: "/app/chat/:id?", route: "/app/chat" });
    await waitFor(() => expect(screen.getByLabelText("Сообщение")).toBeEnabled());
    await userEvent.type(screen.getByLabelText("Сообщение"), "вопрос{Enter}");
    expect(await screen.findByText("GigaChat недоступен")).toBeInTheDocument();
    expect(screen.getByLabelText("Сообщение")).toHaveValue("вопрос");
  });

  it("attaches a document and shows the check results", async () => {
    const sent = {
        conversation: { ...CONV, id: "c2" },
        user_message: { id: "u", role: "user", content: "Проверь документ «договор.pdf»", sources: [], mode: null, model: null, created_at: CONV.created_at,
          attachment: { filename: "договор.pdf", kind: "pdf", size: 2048, chars: 1500, recognized_by: "text_layer", truncated: false } },
        assistant_message: { id: "a", role: "assistant", content: "Демо-режим: проверка выполнена.", sources: [], mode: "demo", model: null, created_at: CONV.created_at,
          findings: [
            { status: "CONTRADICTED", text: "Ставка по покупкам — 39,9% годовых.", explanation: "", source: "Тарифы по кредитной карте «Берег 120»", section: "1. Процентные ставки", quote: "Процентная ставка по операциям покупок — 29,9% годовых." },
            { status: "CONFIRMED", text: "Минимальный платёж — 3%.", explanation: "", source: null, section: null, quote: null }] },
    };
    const { fn } = mockApi({
      "GET /api/v1/banks": [BANK],
      "GET /api/health": { status: "ok", version: "t", default_mode: "demo", live_available: false, database: "ok" },
      "GET /api/v1/chat/conversations": [],
      "GET /api/v1/chat/conversations/c2": { ...CONV, id: "c2", messages: [sent.user_message, sent.assistant_message] },
      "POST /api/v1/chat/documents": sent,
    });
    renderWithApp(<Chat />, { path: "/app/chat/:id?", route: "/app/chat" });
    await waitFor(() => expect(screen.getByLabelText("Сообщение")).toBeEnabled());
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, new File(["%PDF-1.4 test"], "договор.pdf", { type: "application/pdf" }));
    expect(screen.getByText("договор.pdf")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Отправить" }));

    expect(await screen.findByText(/39,9% годовых/)).toBeInTheDocument();
    expect(screen.getByText("Расхождения · 1")).toBeInTheDocument();
    expect(screen.getByText("Подтверждено · 1")).toBeInTheDocument();
    const [, init] = fn.mock.calls.find(([u]) => String(u).includes("/chat/documents"))!;
    const form = init!.body as FormData;
    expect((form.get("file") as File).name).toBe("договор.pdf");
    expect(form.get("mode")).toBe("demo");
  });

  it("rejects unsupported files before upload", async () => {
    mockApi({ "GET /api/v1/banks": [BANK], "GET /api/health": { status: "ok", version: "t", default_mode: "demo", live_available: false, database: "ok" }, "GET /api/v1/chat/conversations": [] });
    renderWithApp(<Chat />, { path: "/app/chat/:id?", route: "/app/chat" });
    await waitFor(() => expect(screen.getByLabelText("Сообщение")).toBeEnabled());
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, new File(["x"], "программа.exe"), { applyAccept: false });
    expect(await screen.findByRole("alert")).toHaveTextContent("Подходят PDF, Word");
  });
});
