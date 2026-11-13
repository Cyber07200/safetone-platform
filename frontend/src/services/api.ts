import type {
  Bank, DocumentDetail, DocumentItem, Health, HistoryPage, ProcessInput, Product, ProvidersView, RunDetail,
  Scenario, SettingsView, Stats, BankSettings, ChatConversation, ChatConversationDetail, ChatSendResponse, Mode,
} from "../types/api";
import { chatOwner } from "../lib/chatOwner";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function request<T>(path: string, init?: RequestInit & { query?: Record<string, unknown> }): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  Object.entries(init?.query ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  });
  let res: Response;
  try {
    res = await fetch(url.toString(), init);
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Сервер SafeTone недоступен. Проверьте, что backend запущен.");
  }
  if (res.status === 204) return undefined as T;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON */
  }
  if (!res.ok) {
    const err = (body as { error?: { code: string; message: string; details?: unknown } } | null)?.error;
    throw new ApiError(res.status, err?.code ?? "HTTP_ERROR", err?.message ?? `Ошибка ${res.status}`, err?.details);
  }
  return body as T;
}

const json = (method: string, data: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
});

const owned = (init: RequestInit = {}): RequestInit => ({ ...init, headers: { ...init.headers, "X-Chat-Owner": chatOwner() } });

export const api = {
  chats: (bank_id: string) => request<ChatConversation[]>("/api/v1/chat/conversations", { ...owned(), query: { bank_id } }),
  chat: (id: string) => request<ChatConversationDetail>(`/api/v1/chat/conversations/${id}`, owned()),
  sendChat: (data: { bank_id: string; conversation_id?: string | null; content: string; mode?: Mode }) =>
    request<ChatSendResponse>("/api/v1/chat/messages", owned(json("POST", data))),
  sendChatDocument: (form: FormData) => request<ChatSendResponse>("/api/v1/chat/documents", owned({ method: "POST", body: form })),
  renameChat: (id: string, title: string) => request<ChatConversation>(`/api/v1/chat/conversations/${id}`, owned(json("PATCH", { title }))),
  deleteChat: (id: string) => request<void>(`/api/v1/chat/conversations/${id}`, owned({ method: "DELETE" })),
  health: () => request<Health>("/api/health"),
  banks: () => request<Bank[]>("/api/v1/banks"),
  products: (bank_id: string) => request<Product[]>("/api/v1/products", { query: { bank_id } }),
  scenarios: (bank_id: string) => request<Scenario[]>("/api/v1/scenarios", { query: { bank_id } }),
  process: (input: ProcessInput) => request<RunDetail>("/api/v1/process", json("POST", input)),
  run: (bank_id: string, id: string) => request<RunDetail>(`/api/v1/process/${id}`, { query: { bank_id } }),
  rerun: (bank_id: string, id: string) =>
    request<RunDetail>(`/api/v1/process/${id}/rerun`, { method: "POST", query: { bank_id } }),
  history: (q: Record<string, unknown>) => request<HistoryPage>("/api/v1/history", { query: q }),
  stats: (bank_id: string) => request<Stats>("/api/v1/stats", { query: { bank_id } }),
  documents: (bank_id: string, q?: Record<string, unknown>) =>
    request<DocumentItem[]>("/api/v1/documents", { query: { bank_id, ...q } }),
  document: (bank_id: string, id: string) => request<DocumentDetail>(`/api/v1/documents/${id}`, { query: { bank_id } }),
  uploadDocument: (form: FormData) => request<DocumentItem>("/api/v1/documents", { method: "POST", body: form }),
  patchDocument: (bank_id: string, id: string, data: Partial<DocumentItem>) =>
    request<DocumentItem>(`/api/v1/documents/${id}`, { ...json("PATCH", data), query: { bank_id } }),
  deleteDocument: (bank_id: string, id: string) =>
    request<void>(`/api/v1/documents/${id}`, { method: "DELETE", query: { bank_id } }),
  providers: () => request<ProvidersView>("/api/v1/providers"),
  checkProvider: (name: string) =>
    request<{ provider: string; ok: boolean; code?: string; message?: string; model?: string; latency_ms?: number }>(
      `/api/v1/providers/${name}/check`, { method: "POST" }),
  settings: (bank_id: string) => request<SettingsView>("/api/v1/settings", { query: { bank_id } }),
  saveSettings: (bank_id: string, data: Partial<BankSettings>) =>
    request<SettingsView>("/api/v1/settings", { ...json("PUT", data), query: { bank_id } }),
};
