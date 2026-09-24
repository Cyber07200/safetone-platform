import { useState, type ReactNode } from "react";
import clsx from "clsx";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, BookMarked, ChevronDown, ExternalLink, FileWarning, ShieldCheck, ShieldAlert, Info } from "lucide-react";
import type { Claim, RunDetail, Source } from "../../types/api";
import { ACTIONS, ACTUALITY, CLAIM, DOC_TYPES, ORIGIN } from "../../lib/labels";
import { fmtDate, fmtMs } from "../../lib/format";
import { ActualityBadge, Badge, ClaimBadge, DemoBadge, ResultBadge, RiskBadge } from "../../components/ui";
import { DiffText } from "../workspace/DiffText";

function Section({ n, title, children, index, aside }: { n: number; title: string; children: ReactNode; index: number; aside?: ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.section initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.05, 0.5) }} className="border-t hairline py-5 first:border-t-0 first:pt-0" aria-labelledby={`audit-${n}`}>
      <div className="mb-3 flex items-center gap-3">
        <span className="font-mono text-[11px] text-brand-600">{String(n).padStart(2, "0")}</span>
        <h3 id={`audit-${n}`} className="text-[15px] font-semibold text-ink-950">{title}</h3>
        {aside && <div className="ml-auto">{aside}</div>}
      </div>
      {children}
    </motion.section>
  );
}

function TextBlock({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "final" }) {
  return (
    <div className={clsx("whitespace-pre-line rounded-lg border px-4 py-3 text-[14px] leading-relaxed",
      tone === "final" ? "border-brand-200 bg-brand-50/50 text-ink-900" : "hairline bg-ink-50/60 text-ink-800")}>{children}</div>
  );
}

function EvidenceQuote({ e }: { e: Claim["evidence"][number] }) {
  const rel = { supports: ["Подтверждает", "ok"], contradicts: ["Противоречит", "bad"], related: ["Связанное положение", "muted"], matches_outdated: ["Совпадает с неактуальной версией", "warn"] } as const;
  const [label, tone] = rel[e.relation];
  return (
    <div className="rounded-lg border hairline bg-white p-3">
      <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[12px]">
        <Badge tone={tone}>{label}</Badge>
        <span className="font-medium text-ink-800">{e.title}</span>
        <span className="text-ink-500">· v{e.version}{e.section ? ` · ${e.section}` : ""}{e.page ? ` · стр. ${e.page}` : ""}</span>
        <ActualityBadge a={e.actuality} />
        {e.is_demo && <DemoBadge />}
      </div>
      <blockquote className="border-l-2 border-brand-200 pl-3 text-[13px] leading-relaxed text-ink-700">«{e.quote}»</blockquote>
      {(e.claim_value || e.source_value) && (
        <div className="mt-2 flex items-center gap-2 font-mono text-[12px]">
          <span className="rounded bg-ink-100 px-1.5 py-0.5 text-ink-700">ответ: {e.claim_value ?? "—"}</span>
          <ArrowRight className="h-3 w-3 text-ink-400" />
          <span className="rounded bg-brand-50 px-1.5 py-0.5 text-brand-800">источник: {e.source_value ?? "—"}</span>
        </div>
      )}
    </div>
  );
}

export function ClaimCard({ c, defaultOpen }: { c: Claim; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const border = { ok: "border-l-ok-600", warn: "border-l-warn-600", bad: "border-l-bad-600", info: "border-l-brand-600", muted: "border-l-ink-300" }[CLAIM[c.status].tone];
  return (
    <div className={clsx("rounded-lg border border-l-[3px] hairline bg-white", border)} data-claim-status={c.status}>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex w-full items-start gap-3 p-3 text-left">
        <span className="mt-0.5 font-mono text-[11px] text-ink-400">{c.id}</span>
        <span className="flex-1 text-[14px] leading-relaxed text-ink-900">{c.text}</span>
        <span className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center">
          <ClaimBadge status={c.status} /><RiskBadge risk={c.risk} />
        </span>
        <ChevronDown className={clsx("mt-0.5 h-4 w-4 shrink-0 text-ink-400 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-3 border-t hairline px-3 pb-3 pt-3">
          <p className="text-[13px] leading-relaxed text-ink-700">{c.explanation}</p>
          {c.status !== c.evidence_status && <p className="text-[12px] text-ink-500">Результат доказательной проверки: <span className="font-mono">{c.evidence_status}</span>; итоговый статус повышен политикой рисков.</p>}
          {c.notes.map((n) => <p key={n} className="flex gap-1.5 text-[12px] text-ink-600"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />{n}</p>)}
          {c.flags.length > 0 && <div className="flex flex-wrap gap-1.5">{c.flags.map((f) => <Badge key={f} mono tone="muted">{{ commitment: "обещание", absolute_wording: "абсолютная формулировка", legal_reference: "ссылка на нормы" }[f] ?? f}</Badge>)}</div>}
          {c.evidence.length > 0 ? <div className="space-y-2">{c.evidence.map((e, i) => <EvidenceQuote key={e.chunk_id + i} e={e} />)}</div>
            : <p className="flex items-center gap-1.5 text-[12px] text-warn-700"><FileWarning className="h-3.5 w-3.5" />Подходящий источник в базе знаний не найден.</p>}
          <div className="flex flex-wrap items-center gap-2 text-[12px]">
            <span className="label-mono">Действие</span><span className="font-medium text-ink-800">{ACTIONS[c.action] ?? c.action}</span>
          </div>
          {c.correction && <div className="rounded-md bg-ok-50 px-3 py-2 text-[13px] text-ok-700"><span className="label-mono mr-2 text-ok-700">Исправление</span>{c.correction}</div>}
        </div>
      )}
    </div>
  );
}

export function SourceCard({ s }: { s: Source }) {
  return (
    <div className="rounded-lg border hairline bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <BookMarked className="h-4 w-4 text-brand-600" />
        <span className="text-[13px] font-medium text-ink-900">{s.title}</span>
        <Badge>{DOC_TYPES[s.doc_type] ?? s.doc_type}</Badge>
        <ActualityBadge a={s.actuality} />
        {s.is_demo && <DemoBadge />}
      </div>
      <div className="mt-1.5 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] text-ink-600">
        <span>Версия: <b className="font-medium text-ink-800">{s.version}</b></span>
        <span>Раздел: <b className="font-medium text-ink-800">{s.section || "—"}</b></span>
        <span>Документ от: <b className="font-medium text-ink-800">{fmtDate(s.document_date)}</b></span>
        <span>Действует: <b className="font-medium text-ink-800">{s.effective_from ? `с ${fmtDate(s.effective_from)}` : "—"}{s.effective_to ? ` по ${fmtDate(s.effective_to)}` : ""}</b></span>
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-ink-700">«{s.quote}»</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px] text-ink-500">
        Использован для: {s.used_for.map((u, i) => <span key={i} className="font-mono">{u.claim_id}</span>)}
        {s.source_url && <a href={s.source_url} target="_blank" rel="noreferrer noopener" className="ml-auto inline-flex items-center gap-1 text-brand-700 hover:underline">Источник <ExternalLink className="h-3 w-3" /></a>}
      </div>
    </div>
  );
}

export function AuditView({ run }: { run: RunDetail }) {
  const substantive = run.claims.filter((c) => c.substantive);
  const service = run.claims.filter((c) => !c.substantive);
  const sem = run.semantic_check;
  let i = 0;
  return (
    <div data-testid="audit-view">
      <Section n={1} title="Вопрос пользователя" index={i++}><TextBlock>{run.question}</TextBlock></Section>

      <Section n={2} title="Исходный ответ" index={i++} aside={<Badge tone={run.answer_origin === "provider" ? "info" : "warn"} mono>{ORIGIN[run.answer_origin]}</Badge>}>
        {run.original_answer ? <TextBlock>{run.original_answer}</TextBlock> : <p className="text-[13px] text-ink-500">Исходный ответ не получен.</p>}
      </Section>

      <Section n={3} title={`Проверяемые утверждения · ${substantive.length}`} index={i++}>
        {substantive.length ? <div className="space-y-2">{substantive.map((c) => <ClaimCard key={c.id} c={c} defaultOpen={c.status !== "CONFIRMED"} />)}</div>
          : <p className="text-[13px] text-ink-500">Проверяемых утверждений не найдено.</p>}
        {service.length > 0 && <p className="mt-2 text-[12px] text-ink-500">Служебные фразы без фактов (не проверялись): {service.map((c) => `«${c.text}»`).join(" ")}</p>}
      </Section>

      <Section n={4} title={`Источники · ${run.sources.length}`} index={i++}>
        {run.sources.length ? <div className="grid gap-2 xl:grid-cols-2">{run.sources.map((s) => <SourceCard key={s.chunk_id} s={s} />)}</div>
          : <p className="text-[13px] text-warn-700">Источники не использовались — ни одно утверждение не подтверждено документами.</p>}
      </Section>

      <Section n={5} title="Статусы и риски" index={i++}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-left text-[13px]">
            <thead><tr className="label-mono border-b hairline"><th className="py-2 pr-3 font-normal">ID</th><th className="py-2 pr-3 font-normal">Статус</th><th className="py-2 pr-3 font-normal">Риск</th><th className="py-2 font-normal">Действие</th></tr></thead>
            <tbody>{substantive.map((c) => (
              <tr key={c.id} className="border-b hairline last:border-0"><td className="py-2 pr-3 font-mono text-[12px] text-ink-500">{c.id}</td><td className="py-2 pr-3"><ClaimBadge status={c.status} /></td><td className="py-2 pr-3"><RiskBadge risk={c.risk} /></td><td className="py-2 text-ink-700">{ACTIONS[c.action] ?? c.action}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </Section>

      <Section n={6} title="Найденные юридические проблемы" index={i++}>
        {run.legal_changes.length === 0 && run.missing_data.length === 0 ? (
          <p className="flex items-center gap-2 text-[13px] text-ok-700"><ShieldCheck className="h-4 w-4" />Существенных проблем не найдено — ответ прошёл без изменений.</p>
        ) : (
          <div className="space-y-2">
            {run.legal_changes.map((ch) => (
              <div key={ch.claim_id} className="rounded-lg border hairline bg-white p-3 text-[13px]">
                <div className="mb-2 flex flex-wrap items-center gap-2"><span className="font-mono text-[11px] text-ink-400">{ch.claim_id}</span><span className="font-medium text-ink-900">{ACTIONS[ch.action] ?? ch.action}</span><RiskBadge risk={ch.risk} /></div>
                <DiffText before={ch.before} after={ch.after ?? ""} />
                <p className="mt-2 text-[12px] text-ink-600">Основание: {ch.reason}</p>
                {ch.basis.map((b, k) => <p key={k} className="text-[12px] text-ink-500">· {b.title}, v{b.version}{b.section ? `, ${b.section}` : ""} — {ACTUALITY[b.actuality as keyof typeof ACTUALITY]?.label ?? b.actuality}</p>)}
              </div>
            ))}
            {run.missing_data.length > 0 && (
              <div className="rounded-lg border border-warn-600/25 bg-warn-50 p-3">
                <div className="mb-1 flex items-center gap-2 text-[13px] font-medium text-warn-700"><ShieldAlert className="h-4 w-4" />Каких данных не хватает</div>
                <ul className="list-disc space-y-0.5 pl-5 text-[13px] text-warn-700">{run.missing_data.map((m) => <li key={m}>{m}</li>)}</ul>
              </div>
            )}
          </div>
        )}
      </Section>

      <Section n={7} title="Юридически скорректированный ответ" index={i++}>
        {run.legal_answer ? <TextBlock>{run.legal_answer}</TextBlock> : <p className="text-[13px] text-ink-500">Этап не выполнен.</p>}
      </Section>

      <Section n={8} title="Изменения лингвистического слоя" index={i++} aside={run.linguistic?.tone_label && <Badge>{run.linguistic.tone_label}</Badge>}>
        {run.linguistic?.method ? (<>
          <p className="mb-2 text-[12px] text-ink-500">Метод: <span className="font-mono">{run.linguistic.method}</span></p>
          {run.linguistic.changes?.length ? <ul className="space-y-1 text-[13px] text-ink-700">{run.linguistic.changes.map((c, k) => <li key={k} className="flex gap-2"><span className="text-brand-600">—</span>{c.description}</li>)}</ul>
            : <p className="text-[13px] text-ink-500">Текст уже простой — стилистических изменений не потребовалось.</p>}
          {run.legal_answer && run.final_answer && <div className="mt-3"><DiffText before={run.legal_answer} after={run.final_answer} /></div>}
        </>) : <p className="text-[13px] text-ink-500">Этап не выполнен.</p>}
      </Section>

      <Section n={9} title="Проверка сохранения смысла" index={i++} aside={sem.passed !== undefined && <Badge tone={sem.passed ? "ok" : "bad"} dot>{sem.passed ? "Смысл сохранён" : "Смысл изменён"}</Badge>}>
        {sem.checks ? (<>
          <ul className="grid gap-1.5 sm:grid-cols-2">{sem.checks.map((c) => (
            <li key={c.name} className="flex items-start gap-2 rounded-md bg-ink-50/70 px-3 py-2 text-[13px]">
              <span className={clsx("mt-1 h-2 w-2 shrink-0 rounded-full", c.passed ? "bg-ok-600" : "bg-bad-600")} />
              <span><span className="font-medium text-ink-900">{c.title}</span><span className="block text-[12px] text-ink-500">{c.detail}</span></span>
            </li>))}</ul>
          {sem.fallback && <p className="mt-2 rounded-md bg-warn-50 px-3 py-2 text-[13px] text-warn-700">Первая версия упрощения изменила смысл и была отклонена. Использовано: {sem.fallback === "offline_rewriter" ? "офлайн-редактор" : "юридически скорректированный текст без упрощения"}.</p>}
          {sem.attempts && sem.attempts.length > 1 && <p className="mt-1 text-[12px] text-ink-500">Попытки: {sem.attempts.map((a) => `${a.method} — ${a.passed ? "прошла" : "отклонена"}`).join("; ")}</p>}
        </>) : <p className="text-[13px] text-ink-500">Этап не выполнен.</p>}
      </Section>

      <Section n={10} title="Финальный ответ" index={i++}>
        {run.final_answer ? <TextBlock tone="final">{run.final_answer}</TextBlock> : <p className="text-[13px] text-bad-700">Финальный ответ не сформирован: обработка завершилась ошибкой.</p>}
      </Section>

      <Section n={11} title="Статус результата" index={i++}>
        <div className="flex flex-wrap items-center gap-3"><ResultBadge status={run.result_status} /><span className="text-[13px] text-ink-600">Максимальный риск исходного ответа:</span><RiskBadge risk={run.max_risk} /></div>
        {run.notices.length > 0 && <ul className="mt-2 space-y-1 text-[13px] text-ink-700">{run.notices.map((n) => <li key={n}>· {n}</li>)}</ul>}
        {run.error && <p className="mt-2 rounded-md bg-bad-50 px-3 py-2 text-[13px] text-bad-700">Ошибка на этапе «{run.error.stage}»: {run.error.message} <span className="font-mono text-[11px]">({run.error.code})</span></p>}
      </Section>

      <Section n={12} title="Модель и режим работы" index={i++}>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-4">
          <div><dt className="label-mono">Режим</dt><dd className="mt-0.5 font-medium">{run.mode === "demo" ? <Badge tone="warn" mono>DEMO MODE</Badge> : <Badge tone="info" mono>LIVE</Badge>}</dd></div>
          <div><dt className="label-mono">Источник ответа</dt><dd className="mt-0.5 text-ink-800">{ORIGIN[run.answer_origin]}</dd></div>
          <div><dt className="label-mono">Провайдер / модель</dt><dd className="mt-0.5 break-all text-ink-800">{run.provider ? `${run.provider} · ${run.model}` : "не использовались"}</dd></div>
          <div><dt className="label-mono">Время</dt><dd className="mt-0.5 text-ink-800">{fmtMs(run.duration_ms)}{run.tokens_total ? ` · ${run.tokens_total} ток.` : ""}{run.cost_estimate !== null ? ` · ≈${run.cost_estimate}` : ""}</dd></div>
        </dl>
        {run.ai_calls.length > 0 && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[12px]">
              <thead><tr className="label-mono border-b hairline"><th className="py-1.5 pr-3 font-normal">Задача</th><th className="py-1.5 pr-3 font-normal">Провайдер</th><th className="py-1.5 pr-3 font-normal">Результат</th><th className="py-1.5 pr-3 font-normal">Задержка</th><th className="py-1.5 font-normal">Причина выбора</th></tr></thead>
              <tbody>{run.ai_calls.map((c, k) => (
                <tr key={k} className="border-b hairline last:border-0"><td className="py-1.5 pr-3 font-mono">{c.task}</td><td className="py-1.5 pr-3">{c.provider} · {c.model}</td><td className="py-1.5 pr-3">{c.ok ? <Badge tone="ok">ok</Badge> : <Badge tone="bad" title={c.error ?? ""}>{c.error_code}</Badge>}</td><td className="py-1.5 pr-3">{fmtMs(c.latency_ms)}</td><td className="py-1.5 text-ink-500">{c.selection_reason}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
        <div className="mt-3 flex flex-wrap gap-1.5">{run.stages.map((s) => <Badge key={s.key} mono tone={s.status === "completed" ? "muted" : s.status === "failed" ? "bad" : "muted"} title={s.summary ?? ""}>{s.key}: {s.method ?? s.status}</Badge>)}</div>
      </Section>
    </div>
  );
}
