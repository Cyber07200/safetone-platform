import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, MessagesSquare, Sparkles } from "lucide-react";
import { api } from "../services/api";
import { useBank } from "../hooks/useBank";
import { useProducts, useProviders } from "../hooks/queries";
import { motion, useReducedMotion } from "framer-motion";
import { Badge, Card, CountUp, EASE, EmptyState, ErrorState, PageHeader, ResultBadge, RiskBadge, Skeleton, FadeIn, buttonClass } from "../components/ui";
import { CLAIM } from "../lib/labels";
import { fmtDate, fmtMs } from "../lib/format";

function Kpi({ label, value, sub, tone, i = 0 }: { label: string; value: number; sub?: string; tone?: "ok" | "warn" | "bad"; i?: number }) {
  const reduce = useReducedMotion();
  const color = tone === "ok" ? "text-ok-700" : tone === "warn" ? "text-warn-700" : tone === "bad" ? "text-bad-700" : "text-ink-950";
  return (
    <motion.div initial={reduce ? false : { opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.7, delay: i * 0.07, ease: EASE }}
      className="card card-hover p-4">
      <div className="label-mono">{label}</div>
      <CountUp value={value} className={`mt-2 block font-display text-[36px] font-semibold tabular-nums tracking-[-0.03em] ${color}`} />
      {sub && <div className="mt-0.5 text-[12px] text-ink-500">{sub}</div>}
    </motion.div>
  );
}

export default function Overview() {
  const { bankId, bank } = useBank();
  const stats = useQuery({ queryKey: ["stats", bankId], queryFn: () => api.stats(bankId!), enabled: !!bankId });
  const providers = useProviders();
  const products = useProducts();
  const reduce = useReducedMotion();
  const s = stats.data;
  const claimsTotal = s ? Object.values(s.claims_by_status).reduce((a, b) => a + b, 0) : 0;

  return (
    <>
      <PageHeader eyebrow="Обзор" title={bank?.name ?? "SafeTone"}
        description="Показатели рассчитаны по реальным обработкам в этой установке SafeTone. В демонстрационном банке все документы и условия вымышлены."
        actions={<Link to="/app/workspace" className={buttonClass()}><Sparkles className="h-4 w-4" />Новая проверка</Link>} />
      {stats.isError && <ErrorState error={stats.error} onRetry={() => stats.refetch()} />}
      {stats.isLoading && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)}</div>}
      {s && (
        <FadeIn>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Обработок" value={s.total_runs} sub={`Demo: ${s.by_mode.demo ?? 0} · Live: ${s.by_mode.live ?? 0}`} />
            <Kpi i={1} label="READY" value={s.by_status.READY ?? 0} tone="ok" sub="готовы к отправке" />
            <Kpi i={2} label="NEEDS REVIEW" value={s.by_status.NEEDS_REVIEW ?? 0} tone="warn" sub="черновик для специалиста" />
            <Kpi i={3} label="FAILED" value={s.by_status.FAILED ?? 0} tone={(s.by_status.FAILED ?? 0) ? "bad" : undefined} sub="ошибки провайдеров / обработки" />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <Card className="h-fit p-5">
              <div className="mb-3 flex items-center justify-between"><span className="label-mono">Последние обработки</span><Link to="/app/history" className="text-[12px] font-medium text-brand-700 hover:underline">История</Link></div>
              {s.recent.length === 0 ? (
                <EmptyState title="Обработок пока нет" description="Запустите первый демо-сценарий в AI Workspace — результат и аудит сохранятся здесь."
                  action={<Link to="/app/workspace" className={buttonClass("primary", "sm")}>Открыть Workspace</Link>} />
              ) : (
                <ul className="divide-y divide-ink-100">
                  {s.recent.map((r, i) => (
                    <motion.li key={r.id} initial={reduce ? false : { opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.2 + i * 0.04, ease: EASE }}>
                      <Link to={`/app/runs/${r.id}`} className="group flex flex-wrap items-center gap-3 py-3">
                        <span className="min-w-0 flex-1 truncate text-[14px] text-ink-900 group-hover:text-brand-700">{r.question}</span>
                        <RiskBadge risk={r.max_risk} /><ResultBadge status={r.result_status} />
                        <span className="w-full font-mono text-[11px] text-ink-400 sm:w-auto">{fmtDate(r.created_at, true)} · {r.mode.toUpperCase()}</span>
                      </Link>
                    </motion.li>
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
                      {Object.entries(s.claims_by_status).map(([k, v], i) => {
                        const t = CLAIM[k as keyof typeof CLAIM]?.tone;
                        const c = t === "ok" ? "bg-ok-600" : t === "bad" ? "bg-bad-600" : "bg-warn-600";
                        const w = `${(v / claimsTotal) * 100}%`;
                        return <motion.div key={k} className={c} initial={reduce ? false : { width: 0 }} animate={{ width: w }} transition={{ duration: 1, delay: 0.3 + i * 0.1, ease: EASE }} title={`${k}: ${v}`} />;
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
                <div className="mb-3 flex items-center justify-between"><span className="label-mono">Продукты банка · {products.data?.length ?? 0}</span>
                  <Link to="/app/chat" className="group inline-flex items-center gap-1 text-[12px] font-medium text-brand-700 hover:underline"><MessagesSquare className="h-3.5 w-3.5" />Спросить</Link></div>
                <ul className="space-y-2">
                  {products.data?.map((p) => (
                    <li key={p.id}><div className="text-[13px] font-medium text-ink-900">{p.name}</div><div className="text-[12px] leading-snug text-ink-500">{p.description.replace(" Демонстрационный продукт.", "")}</div></li>
                  ))}
                </ul>
              </Card>
              <Card className="p-5">
                <div className="mb-2 flex items-center justify-between"><span className="label-mono">База знаний</span><BookOpen className="h-4 w-4 text-ink-400" /></div>
                <div className="text-[14px] text-ink-800">{s.documents} документов</div>
                {s.documents_needing_attention > 0 && <p className="mt-1 text-[13px] text-warn-700">{s.documents_needing_attention} — заменены, утратили силу или без подтверждённой актуальности</p>}
                <Link to="/app/knowledge" className="group mt-3 inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline">Управлять источниками <ArrowRight className="arrow-nudge h-3.5 w-3.5" /></Link>
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
