import { useEffect, useState } from "react";
import clsx from "clsx";
import { motion, useReducedMotion } from "framer-motion";
import { Check, CircleDashed, Loader2, Minus, X } from "lucide-react";
import type { Stage } from "../../types/api";
import { fmtMs } from "../../lib/format";

const DEFAULT: Pick<Stage, "key" | "title">[] = [
  { key: "generation", title: "Генерация ответа AI" },
  { key: "claim_extraction", title: "Извлечение утверждений" },
  { key: "source_retrieval", title: "Поиск источников" },
  { key: "legal_verification", title: "Юридическая проверка" },
  { key: "legal_correction", title: "Юридическая корректировка" },
  { key: "linguistic_rewrite", title: "Лингвистическая обработка" },
  { key: "semantic_validation", title: "Проверка сохранения смысла" },
  { key: "final_response", title: "Финальный ответ" },
];

/**
 * Shows the REAL stage states reported by the backend. Stages that are
 * already completed are revealed one after another (presentation only);
 * nothing is ever shown as completed before the backend says so.
 */
export function PipelineProgress({ stages, compact, layout = "list" }: { stages?: Stage[]; compact?: boolean; layout?: "list" | "grid" }) {
  const reduce = useReducedMotion();
  const list: Stage[] = stages?.length ? stages : DEFAULT.map((s) => ({ ...s, status: "pending", method: null, summary: null, started_at: null, finished_at: null, duration_ms: null, warnings: [] }));
  const doneCount = list.filter((s) => s.status !== "pending" && s.status !== "running").length;
  const [shown, setShown] = useState(reduce ? doneCount : 0);
  useEffect(() => {
    if (reduce) { setShown(doneCount); return; }
    if (shown >= doneCount) { if (doneCount < shown) setShown(doneCount); return; }
    const t = setTimeout(() => setShown((n) => n + 1), 110);
    return () => clearTimeout(t);
  }, [doneCount, shown, reduce]);

  return (
    <ol className={clsx("relative", layout === "grid" ? "grid gap-x-6 sm:grid-cols-2 xl:grid-cols-4" : compact ? "space-y-1" : "space-y-0")} aria-label="Этапы обработки">
      {list.map((s, i) => {
        const revealed = i < shown;
        const status = revealed ? s.status : (s.status === "running" || (i === shown && doneCount > shown) ? "running" : "pending");
        const last = i === list.length - 1;
        return (
          <li key={s.key} className="relative flex gap-3 pb-3" data-stage={s.key} data-status={revealed ? s.status : status}>
            {!last && layout === "list" && <span className={clsx("absolute left-[11px] top-6 h-[calc(100%-18px)] w-px", revealed && s.status === "completed" ? "bg-ok-600/40" : "bg-ink-200")} />}
            <motion.span layout className={clsx("relative z-10 mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full border text-white",
              status === "completed" && "border-ok-600 bg-ok-600",
              status === "failed" && "border-bad-600 bg-bad-600",
              status === "running" && "border-brand-500 bg-white text-brand-600",
              status === "skipped" && "border-ink-300 bg-ink-100 text-ink-400",
              status === "pending" && "border-ink-200 bg-white text-ink-300")}>
              {status === "completed" && <motion.span initial={reduce ? false : { scale: 0 }} animate={{ scale: 1 }}><Check className="h-3.5 w-3.5" strokeWidth={3} /></motion.span>}
              {status === "failed" && <X className="h-3.5 w-3.5" strokeWidth={3} />}
              {status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {status === "skipped" && <Minus className="h-3.5 w-3.5" />}
              {status === "pending" && <CircleDashed className="h-3.5 w-3.5" />}
            </motion.span>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className={clsx("text-[13px] font-medium", status === "pending" ? "text-ink-400" : "text-ink-900")}>
                  <span className="mr-1.5 font-mono text-[11px] text-ink-400">{String(i + 1).padStart(2, "0")}</span>{s.title}
                </span>
                {revealed && s.duration_ms !== null && <span className="font-mono text-[11px] text-ink-400">{fmtMs(s.duration_ms)}</span>}
              </div>
              {!compact && revealed && s.summary && (
                <motion.p initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} className={clsx("mt-0.5 text-[12px] leading-snug", s.status === "failed" ? "text-bad-700" : "text-ink-500")}>
                  {s.summary}
                </motion.p>
              )}
              {!compact && revealed && s.warnings?.map((w) => <p key={w} className="mt-0.5 text-[12px] leading-snug text-warn-700">Внимание: {w}</p>)}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
