import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { motion, useReducedMotion } from "framer-motion";
import { AlertOctagon, Check, CheckCircle2, Copy, ExternalLink, RotateCcw, ShieldAlert } from "lucide-react";
import type { RunDetail } from "../../types/api";
import { CLAIM, ORIGIN, RESULT } from "../../lib/labels";
import { fmtMs } from "../../lib/format";
import { Badge, Button, ResultBadge, RiskBadge, Segmented } from "../../components/ui";
import { AuditView } from "../audit/AuditView";
import { DiffText } from "./DiffText";

function StatusBanner({ run }: { run: RunDetail }) {
  const s = run.result_status ?? "FAILED";
  const Icon = s === "READY" ? CheckCircle2 : s === "NEEDS_REVIEW" ? ShieldAlert : AlertOctagon;
  const cls = { READY: "border-ok-600/25 bg-ok-50 text-ok-700", NEEDS_REVIEW: "border-warn-600/30 bg-warn-50 text-warn-700", FAILED: "border-bad-600/25 bg-bad-50 text-bad-700" }[s];
  const changes = run.legal_changes.length;
  return (
    <div className={clsx("flex flex-wrap items-center gap-3 rounded-xl2 border px-4 py-3", cls)} data-testid="status-banner" data-status={s}>
      <Icon className="h-5 w-5 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2"><ResultBadge status={s} /><span className="text-[14px] font-medium">{RESULT[s].hint}</span></div>
        <div className="mt-0.5 text-[12px] opacity-90">
          {s === "FAILED" ? run.error?.message :
            changes === 0 ? "Юридический слой не внёс изменений — все существенные утверждения подтверждены." :
              `Юридический слой внёс изменений: ${changes}. Все основания — в подробном аудите.`}
        </div>
      </div>
      {run.mode === "demo" && <Badge tone="warn" mono title={ORIGIN[run.answer_origin]}>DEMO MODE</Badge>}
    </div>
  );
}

export function ResultView({ run, onRerun, rerunning }: { run: RunDetail; onRerun?: () => void; rerunning?: boolean }) {
  const [view, setView] = useState<"result" | "audit">("result");
  const [cmp, setCmp] = useState<"full" | "legal" | "linguistic">("full");
  const [copied, setCopied] = useState(false);
  const reduce = useReducedMotion();
  const substantive = run.claims.filter((c) => c.substantive);
  const counts = substantive.reduce<Record<string, number>>((a, c) => ({ ...a, [c.status]: (a[c.status] ?? 0) + 1 }), {});

  const copy = async () => {
    if (!run.final_answer) return;
    try { await navigator.clipboard.writeText(run.final_answer); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch { /* clipboard blocked */ }
  };

  const pair = cmp === "full" ? [run.original_answer, run.final_answer] : cmp === "legal" ? [run.original_answer, run.legal_answer] : [run.legal_answer, run.final_answer];
  const labels = cmp === "full" ? ["Исходный ответ AI", "Итоговый ответ"] : cmp === "legal" ? ["Исходный ответ AI", "После юридического слоя"] : ["После юридического слоя", "После лингвистического слоя"];

  return (
    <div className="space-y-4" data-testid="result-view">
      <StatusBanner run={run} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="w-full sm:w-auto sm:min-w-[300px]">
          <Segmented ariaLabel="Вид результата" value={view} onChange={setView} options={[{ value: "result", label: "Результат" }, { value: "audit", label: "Подробный аудит" }]} />
        </div>
        <div className="flex flex-wrap gap-2">
          {onRerun && <Button variant="secondary" size="sm" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={onRerun} loading={rerunning}>Повторить</Button>}
          <Link to={`/app/runs/${run.id}`}><Button variant="ghost" size="sm" icon={<ExternalLink className="h-3.5 w-3.5" />}>Открыть аудит</Button></Link>
        </div>
      </div>

      {view === "result" ? (
        <motion.div key="result" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b hairline px-4 py-2.5">
              <span className="label-mono">Итоговый ответ клиенту</span>
              <Button variant="ghost" size="sm" onClick={copy} disabled={!run.final_answer} icon={copied ? <Check className="h-3.5 w-3.5 text-ok-600" /> : <Copy className="h-3.5 w-3.5" />}>{copied ? "Скопировано" : "Копировать"}</Button>
            </div>
            <div className="whitespace-pre-line px-4 py-4 text-[15px] leading-relaxed text-ink-900" data-testid="final-answer">
              {run.final_answer ?? <span className="text-bad-700">Итоговый ответ не сформирован.</span>}
            </div>
          </div>

          {run.original_answer && run.final_answer && (
            <div className="card">
              <div className="flex flex-col gap-2 border-b hairline px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between">
                <span className="label-mono">Сравнение версий</span>
                <div className="sm:w-[420px]"><Segmented size="sm" ariaLabel="Сравнение" value={cmp} onChange={setCmp} options={[{ value: "full", label: "До → После" }, { value: "legal", label: "Юр. слой" }, { value: "linguistic", label: "Лингв. слой" }]} /></div>
              </div>
              <div className="grid gap-px bg-ink-200/70 md:grid-cols-2">
                <div className="bg-white p-4"><div className="mb-2 text-[12px] font-medium text-ink-500">{labels[0]}</div><DiffText before={pair[0] ?? ""} after={pair[1] ?? ""} mode="before" /></div>
                <div className="bg-white p-4"><div className="mb-2 text-[12px] font-medium text-ink-500">{labels[1]}</div><DiffText before={pair[0] ?? ""} after={pair[1] ?? ""} mode="after" /></div>
              </div>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="card p-4"><div className="label-mono">Утверждения</div>
              <div className="mt-2 flex flex-wrap gap-1.5">{Object.entries(counts).map(([k, v]) => <Badge key={k} tone={CLAIM[k as keyof typeof CLAIM].tone} mono>{CLAIM[k as keyof typeof CLAIM].label} · {v}</Badge>)}{!substantive.length && <span className="text-[13px] text-ink-500">нет проверяемых</span>}</div></div>
            <div className="card p-4"><div className="label-mono">Макс. риск исходного ответа</div><div className="mt-2"><RiskBadge risk={run.max_risk} />{!run.max_risk && "—"}</div></div>
            <div className="card p-4"><div className="label-mono">Модель · время</div><div className="mt-2 text-[13px] text-ink-800">{run.provider ? `${run.provider} · ${run.model}` : ORIGIN[run.answer_origin]}<span className="text-ink-500"> · {fmtMs(run.duration_ms)}</span></div></div>
          </div>
          {run.missing_data.length > 0 && (
            <div className="rounded-xl2 border border-warn-600/25 bg-warn-50 p-4 text-[13px] text-warn-700">
              <div className="mb-1 font-medium">Не хватает данных для полного ответа</div>
              <ul className="list-disc space-y-0.5 pl-5">{run.missing_data.map((m) => <li key={m}>{m}</li>)}</ul>
            </div>
          )}
        </motion.div>
      ) : (
        <div className="card p-4 sm:p-6"><AuditView run={run} /></div>
      )}
    </div>
  );
}
