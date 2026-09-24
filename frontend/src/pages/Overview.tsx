import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, Sparkles } from "lucide-react";
import { api } from "../services/api";
import { useBank } from "../hooks/useBank";
import { useProviders } from "../hooks/queries";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, ResultBadge, RiskBadge, Skeleton, FadeIn } from "../components/ui";
import { CLAIM } from "../lib/labels";
import { fmtDate, fmtMs } from "../lib/format";

function Kpi({ label, value, sub, tone }: { label: string; value: string | number; sub?: string; tone?: "ok" | "warn" | "bad" }) {
  const color = tone === "ok" ? "text-ok-700" : tone === "warn" ? "text-warn-700" : tone === "bad" ? "text-bad-700" : "text-ink-950";
  return (
    <Card className="p-4">
      <div className="label-mono">{label}</div>
      <div className={`mt-2 text-[28px] font-semibold tabular-nums tracking-[-0.02em] ${color}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[12px] text-ink-500">{sub}</div>}
    </Card>
  );
}

export default function Overview() {
  const { bankId, bank } = useBank();
  const stats = useQuery({ queryKey: ["stats", bankId], queryFn: () => api.stats(bankId!), enabled: !!bankId });
  const providers = useProviders();
  const s = stats.data;
  const claimsTotal = s ? Object.values(s.claims_by_status).reduce((a, b) => a + b, 0) : 0;

  return (
    <>
      <PageHeader eyebrow="Обзор" title={bank?.name ?? "SafeTone"}
        description="Показатели рассчитаны по реальным обработкам в этой установке SafeTone. В демонстрационном банке все документы и условия вымышлены."
        actions={<Link to="/app/workspace"><Button icon={<Sparkles className="h-4 w-4" />}>Новая проверка</Button></Link>} />
      {stats.isError && <ErrorState error={stats.error} onRetry={() => stats.refetch()} />}
      {stats.isLoading && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)}</div>}
      {s && (
        <FadeIn>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Обработок" value={s.total_runs} sub={`Demo: ${s.by_mode.demo ?? 0} · Live: ${s.by_mode.live ?? 0}`} />
            <Kpi label="READY" value={s.by_status.READY ?? 0} tone="ok" sub="готовы к отправке" />
            <Kpi label="NEEDS REVIEW" value={s.by_status.NEEDS_REVIEW ?? 0} tone="warn" sub="черновик для специалиста" />
            <Kpi label="FAILED" value={s.by_status.FAILED ?? 0} tone={(s.by_status.FAILED ?? 0) ? "bad" : undefined} sub="ошибки провайдеров / обработки" />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between"><span className="label-mono">Последние обработки</span><Link to="/app/history" className="text-[12px] font-medium text-brand-700 hover:underline">История</Link></div>
              {s.recent.length === 0 ? (
                <EmptyState title="Обработок пока нет" description="Запустите первый демо-сценарий в AI Workspace — результат и аудит сохранятся здесь."
                  action={<Link to="/app/workspace"><Button size="sm">Открыть Workspace</Button></Link>} />
              ) : (
                <ul className="divide-y divide-ink-100">
                  {s.recent.map((r) => (
                    <li key={r.id}>
                      <Link to={`/app/runs/${r.id}`} className="group flex flex-wrap items-center gap-3 py-3">
                        <span className="min-w-0 flex-1 truncate text-[14px] text-ink-900 group-hover:text-brand-700">{r.question}</span>
                        <RiskBadge risk={r.max_risk} /><ResultBadge status={r.result_status} />
                        <span className="w-full font-mono text-[11px] text-ink-400 sm:w-auto">{fmtDate(r.created_at, true)} · {r.mode.toUpperCase()}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <div className="space-y-4">
              <Card className="p-5">
                <div className="label-mono mb-3">Утверждения по статусам · {claimsTotal}</div>
                {claimsTotal === 0 ? <p className="text-[13px] text-ink-500">Нет данных</p> : (
                  <>
                    <div className="flex h-2.5 overflow-hidden rounded-full bg-ink-100">
                      {Object.entries(s.claims_by_status).map(([k, v]) => {
                        const t = CLAIM[k as keyof typeof CLAIM]?.tone;
                        const c = t === "ok" ? "bg-ok-600" : t === "bad" ? "bg-bad-600" : "bg-warn-600";
                        return <div key={k} className={c} style={{ width: `${(v / claimsTotal) * 100}%` }} title={`${k}: ${v}`} />;
                      })}
                    </div>
                    <ul className="mt-3 space-y-1.5 text-[13px]">
                      {Object.entries(s.claims_by_status).map(([k, v]) => <li key={k} className="flex justify-between"><span className="text-ink-700">{CLAIM[k as keyof typeof CLAIM]?.ru ?? k}</span><span className="font-mono tabular-nums">{v}</span></li>)}
                    </ul>
                  </>
                )}
                <div className="mt-4 border-t hairline pt-3 text-[12px] text-ink-500">Исправлений юридическим слоем: <b className="text-ink-800">{s.corrections}</b> · среднее время: <b className="text-ink-800">{fmtMs(s.avg_duration_ms)}</b></div>
              </Card>
              <Card className="p-5">
                <div className="mb-2 flex items-center justify-between"><span className="label-mono">База знаний</span><BookOpen className="h-4 w-4 text-ink-400" /></div>
                <div className="text-[14px] text-ink-800">{s.documents} документов</div>
                {s.documents_needing_attention > 0 && <p className="mt-1 text-[13px] text-warn-700">{s.documents_needing_attention} — заменены, утратили силу или без подтверждённой актуальности</p>}
                <Link to="/app/knowledge" className="mt-3 inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline">Управлять источниками <ArrowRight className="h-3.5 w-3.5" /></Link>
              </Card>
              <Card className="p-5">
                <div className="label-mono mb-2">AI-провайдеры</div>
                {providers.data?.providers.map((p) => (
                  <div key={p.name} className="flex items-center justify-between py-1 text-[13px]"><span>{p.label}</span>
                    <Badge tone={p.status === "not_configured" ? "muted" : p.status === "unavailable" ? "bad" : p.status === "degraded" ? "warn" : "ok"} dot>{p.status === "not_configured" ? "не настроен" : p.status === "unavailable" ? "недоступен" : p.status === "degraded" ? "с ошибками" : "настроен"}</Badge>
                  </div>
                ))}
              </Card>
            </div>
          </div>
        </FadeIn>
      )}
    </>
  );
}
