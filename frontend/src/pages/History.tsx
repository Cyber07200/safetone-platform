import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { api } from "../services/api";
import { useBank } from "../hooks/useBank";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, ResultBadge, RiskBadge, SkeletonRows } from "../components/ui";
import { fmtDate, fmtMs } from "../lib/format";
import { ORIGIN } from "../lib/labels";

const LIMIT = 15;

export default function History() {
  const { bankId } = useBank();
  const nav = useNavigate();
  const [status, setStatus] = useState("");
  const [mode, setMode] = useState("");
  const [risk, setRisk] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["history", bankId, status, mode, risk, q, offset],
    queryFn: () => api.history({ bank_id: bankId, status, mode, risk, q, limit: LIMIT, offset }),
    enabled: !!bankId, placeholderData: keepPreviousData,
  });
  const reset = (fn: () => void) => { fn(); setOffset(0); };
  const d = query.data;

  return (
    <>
      <PageHeader eyebrow="Processing History" title="История обработок" description="Каждая обработка сохраняется целиком: исходный ответ, результаты слоёв, источники и аудит." />
      <Card className="mb-4 p-3">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_170px_140px_140px]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <input aria-label="Поиск по вопросу" className="field pl-9" placeholder="Поиск по вопросу" value={q} onChange={(e) => reset(() => setQ(e.target.value))} />
          </div>
          <select aria-label="Статус" className="field" value={status} onChange={(e) => reset(() => setStatus(e.target.value))}>
            <option value="">Все статусы</option><option value="READY">READY</option><option value="NEEDS_REVIEW">NEEDS REVIEW</option><option value="FAILED">FAILED</option>
          </select>
          <select aria-label="Режим" className="field" value={mode} onChange={(e) => reset(() => setMode(e.target.value))}>
            <option value="">Все режимы</option><option value="demo">Demo</option><option value="live">Live</option>
          </select>
          <select aria-label="Риск" className="field" value={risk} onChange={(e) => reset(() => setRisk(e.target.value))}>
            <option value="">Любой риск</option>{["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </Card>
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
      {query.isLoading && <SkeletonRows rows={6} />}
      {d && d.items.length === 0 && (
        <EmptyState title={status || mode || risk || q ? "Ничего не найдено" : "История пуста"} description={status || mode || risk || q ? "Измените фильтры." : "Запустите проверку в AI Workspace."}
          action={<Link to="/app/workspace"><Button size="sm">Открыть Workspace</Button></Link>} />
      )}
      {d && d.items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-[13px]">
              <thead className="bg-ink-50/80"><tr className="label-mono">
                <th className="px-4 py-2.5 font-normal">Дата</th><th className="px-4 py-2.5 font-normal">Вопрос</th><th className="px-4 py-2.5 font-normal">Продукт</th>
                <th className="px-4 py-2.5 font-normal">Режим / источник</th><th className="px-4 py-2.5 font-normal">Риск</th><th className="px-4 py-2.5 font-normal">Статус</th><th className="px-4 py-2.5 text-right font-normal">Время</th>
              </tr></thead>
              <tbody>
                {d.items.map((r) => (
                  <tr key={r.id} onClick={() => nav(`/app/runs/${r.id}`)} className="cursor-pointer border-t hairline transition-colors hover:bg-brand-50/40">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-[12px] text-ink-500">{fmtDate(r.created_at, true)}</td>
                    <td className="max-w-[320px] px-4 py-3"><Link to={`/app/runs/${r.id}`} className="line-clamp-2 font-medium text-ink-900 hover:text-brand-700" onClick={(e) => e.stopPropagation()}>{r.question}</Link></td>
                    <td className="px-4 py-3 text-ink-600">{r.product_name ?? "—"}</td>
                    <td className="px-4 py-3"><Badge tone={r.mode === "demo" ? "warn" : "info"} mono>{r.mode.toUpperCase()}</Badge><div className="mt-1 text-[11px] text-ink-500">{r.provider ? `${r.provider} · ${r.model}` : ORIGIN[r.answer_origin]}</div></td>
                    <td className="px-4 py-3"><RiskBadge risk={r.max_risk} /></td>
                    <td className="px-4 py-3"><ResultBadge status={r.result_status} /></td>
                    <td className="px-4 py-3 text-right font-mono text-[12px] text-ink-500">{fmtMs(r.duration_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t hairline px-4 py-2.5 text-[12px] text-ink-500">
            <span>{d.offset + 1}–{d.offset + d.items.length} из {d.total}</span>
            <div className="flex gap-1">
              <Button size="sm" variant="secondary" aria-label="Назад" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))} icon={<ChevronLeft className="h-4 w-4" />} />
              <Button size="sm" variant="secondary" aria-label="Вперёд" disabled={offset + LIMIT >= d.total} onClick={() => setOffset(offset + LIMIT)} icon={<ChevronRight className="h-4 w-4" />} />
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
