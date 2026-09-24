import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { vi } from "vitest";
import { BankProvider } from "../hooks/useBank";

type Handler = (url: URL, init?: RequestInit) => unknown | Promise<unknown>;

/** Routes fetch() calls to handlers keyed by "METHOD /path". */
export function mockApi(routes: Record<string, Handler | unknown>) {
  const calls: { key: string; body?: unknown }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const key = `${(init?.method ?? "GET").toUpperCase()} ${url.pathname}`;
    calls.push({ key, body: init?.body && typeof init.body === "string" ? JSON.parse(init.body) : undefined });
    const route = routes[key];
    if (route === undefined) return new Response(JSON.stringify({ error: { code: "NOT_MOCKED", message: key } }), { status: 404 });
    const value = typeof route === "function" ? await (route as Handler)(url, init) : route;
    if (value instanceof Response) return value;
    return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls };
}

export function renderWithApp(ui: ReactNode, { path = "/", route = "/" }: { path?: string; route?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <BankProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes><Route path={path} element={ui} /><Route path="*" element={<div>other page</div>} /></Routes>
        </MemoryRouter>
      </BankProvider>
    </QueryClientProvider>,
  );
}
