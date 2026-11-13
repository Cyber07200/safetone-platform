import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, KeyRound } from "lucide-react";
import { api } from "../services/api";
import { useProviders } from "../hooks/queries";
import type { ProviderInfo } from "../types/api";
import { Badge, Button, Card, ErrorState, PageHeader, SkeletonRows } from "../components/ui";
import { fmtMs } from "../lib/format";

const STATUS: Record<ProviderInfo["status"], { label: string; tone: "ok" | "warn" | "bad" | "muted" | "info" }> = {
  not_configured: { label: "Не настроен", tone: "muted" }, configured: { label: "Настроен, не проверялся", tone: "info" },
  ok: { label: "Работает", tone: "ok" }, degraded: { label: "Есть ошибки", tone: "warn" }, unavailable: { label: "Временно исключён", tone: "bad" },
};
const ENV = ["# бесплатно для физлиц (Freemium): developers.sber.ru/studio", "GIGACHAT_AUTH_KEY=…  # Authorization key", "GIGACHAT_SCOPE=GIGACHAT_API_PERS", "GIGACHAT_MODEL=GigaChat-2-Max", "# при ошибке TLS: GIGACHAT_CA_BUNDLE=/path/russian_trusted_root_ca.pem"];
const USES = [
  ["Чат-ассистент", "Отвечает с опорой на законы и документы банка из базы знаний, помнит весь диалог."],
  ["Генерация ответа", "Черновик ответа клиенту в AI Workspace (Live Mode)."],
  ["Юридическая проверка", "Дополнительная LLM-верификация утверждений — только с цитатами из источников."],
  ["Понятный язык", "Переписывание ответа в выбранном тоне с проверкой сохранения смысла."],
];

function ProviderCard({ p }: { p: ProviderInfo }) {
  const qc = useQueryClient();
  const [result, setResult] = useState<string | null>(null);
  const check = useMutation({ mutationFn: () => api.checkProvider(p.name), onSuccess: (r) => { setResult(r.ok ? `Ответ получен: ${r.model}, ${fmtMs(r.latency_ms)}` : `${r.code}: ${r.message}`); qc.invalidateQueries({ queryKey: ["providers"] }); } });
  const st = STATUS[p.status];
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div><div className="text-[16px] font-semibold">{p.label}</div><div className="mt-0.5 break-all font-mono text-[12px] text-ink-500">{p.model ?? "модель не задана"}</div></div>
        <Badge tone={st.tone} dot>{st.label}</Badge>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-3 text-[12px]">
        <div><dt className="label-mono">Качество</dt><dd className="mt-0.5 font-medium">{"●".repeat(p.quality_tier)}{"○".repeat(3 - p.quality_tier)}</dd></div>
        <div><dt className="label-mono">Цена / 1K</dt><dd className="mt-0.5 font-medium">{p.cost_per_1k_tokens ?? "не задана"}</dd></div>
        <div><dt className="label-mono">JSON-режим</dt><dd className="mt-0.5 font-medium">{p.supports_json ? "да" : "нет"}</dd></div>
        <div><dt className="label-mono">Вызовов</dt><dd className="mt-0.5 font-medium">{p.calls}</dd></div>
        <div><dt className="label-mono">Ошибок</dt><dd className="mt-0.5 font-medium">{p.failures}</dd></div>
        <div><dt className="label-mono">Задержка</dt><dd className="mt-0.5 font-medium">{fmtMs(p.latency_ema_ms)}</dd></div>
      </dl>
      {!p.configured && (
        <div className="mt-4 rounded-lg bg-ink-50 p-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-medium text-ink-700"><KeyRound className="h-3.5 w-3.5" />Добавьте в backend/.env:</div>
          <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed text-ink-600">{ENV.join("\n")}</pre>
        </div>
      )}
      {p.last_error && <p className="mt-3 text-[12px] text-bad-700">Последняя ошибка: {p.last_error}</p>}
      {result && <p className="mt-3 text-[12px] text-ink-700" role="status">{result}</p>}
      <div className="mt-auto pt-4">
        <Button variant="secondary" size="sm" icon={<Activity className="h-3.5 w-3.5" />} onClick={() => check.mutate()} loading={check.isPending} disabled={!p.configured}
          title={p.configured ? "Выполняет короткий реальный запрос к API (расходует токены)" : "Сначала настройте ключи"}>Проверить доступность</Button>
      </div>
    </Card>
  );
}

export default function Models() {
  const q = useProviders();
  return (
    <>
      <PageHeader eyebrow="Языковая модель" title="GigaChat" description="SafeTone работает с GigaChat через API. Статус ниже отражает реальную конфигурацию и результаты вызовов." />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isLoading && <SkeletonRows rows={3} />}
      {q.data && (
        <>
          {!q.data.live_available && (
            <div className="mb-4 rounded-xl2 border border-warn-600/25 bg-warn-50 p-4 text-[13px] text-warn-700">
              GigaChat не подключён — доступен только <b>Demo Mode</b>. Добавьте ключ в <span className="font-mono">backend/.env</span> и перезапустите backend, чтобы включить Live AI.
            </div>
          )}
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            {q.data.providers.map((p) => <ProviderCard key={p.name} p={p} />)}
            <Card className="p-5">
              <div className="label-mono mb-3">Где SafeTone использует GigaChat</div>
              <ul className="space-y-3">{USES.map(([t, d]) => <li key={t}><div className="text-[14px] font-medium text-ink-900">{t}</div><p className="mt-0.5 text-[13px] leading-relaxed text-ink-600">{d}</p></li>)}</ul>
              <p className="mt-4 border-t hairline pt-3 text-[12px] leading-relaxed text-ink-500">Повторы при сетевых сбоях, тайм-ауты и временное отключение при серии ошибок. Юридическая проверка по источникам работает и без модели.</p>
            </Card>
          </div>
        </>
      )}
    </>
  );
}
