import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import clsx from "clsx";
import { ArrowRight, BookMarked, CheckCircle2, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, DemoBadge, EASE } from "../../components/ui";

/**
 * Illustration of the transformation, using the texts of the demo scenarios
 * (fictional demo bank). The real processing runs in the Workspace.
 */
const EXAMPLES = [
  {
    id: "rate-error", tab: "Ставка",
    question: "Какая ставка по кредитной карте «Берег 120» на покупки?",
    answer: [{ t: "Процентная ставка по операциям покупок составляет " }, { t: "19,9%", bad: true }, { t: " годовых. Льготный период на покупки — до 120 дней." }],
    claims: [{ text: "ставка 19,9% годовых", status: "CONTRADICTED", tone: "bad" as const }, { text: "льготный период до 120 дней", status: "CONFIRMED", tone: "ok" as const }],
    source: { title: "Тарифы по кредитной карте «Берег 120»", ref: "п. 1.1", quote: "Процентная ставка по операциям покупок — 29,9% годовых." },
    final: [{ t: "Процентная ставка по операциям покупок составляет " }, { t: "29,9%", good: true }, { t: " годовых. Льготный период на покупки — до 120 дней." }],
    status: "READY",
  },
  {
    id: "fee-error", tab: "Комиссия",
    question: "Сколько стоит снять наличные с кредитной карты?",
    answer: [{ t: "Снятие наличных в банкоматах любых банков — " }, { t: "без комиссии", bad: true }, { t: "." }],
    claims: [{ text: "снятие наличных без комиссии", status: "CONTRADICTED", tone: "bad" as const }],
    source: { title: "Тарифы по кредитной карте «Берег 120»", ref: "п. 2.2", quote: "Комиссия за снятие наличных в банкоматах любых банков — 3,9% от суммы + 390 ₽." },
    final: [{ t: "Комиссия за снятие наличных в банкоматах любых банков — " }, { t: "3,9% от суммы + 390 ₽", good: true }, { t: "." }],
    status: "READY",
  },
  {
    id: "incomplete-data", tab: "Нет данных",
    question: "Какая ставка по вкладу «Надёжный» на 2 года?",
    answer: [{ t: "По вкладу на срок 24 месяца действует ставка " }, { t: "16% годовых", bad: true }, { t: ". Минимальная сумма вклада — 10 000 ₽." }],
    claims: [{ text: "ставка 16% на 24 месяца", status: "UNVERIFIED", tone: "warn" as const }, { text: "минимальная сумма 10 000 ₽", status: "CONFIRMED", tone: "ok" as const }],
    source: { title: "Условия вклада «Надёжный»", ref: "п. 1.1–1.2", quote: "Процентная ставка по вкладу «Надёжный» на срок 6 месяцев — 14% годовых. … на срок 12 месяцев — 12,5% годовых.", note: "Условия на 24 месяца в источниках нет — значение не подставляется." },
    final: [{ t: "Минимальная сумма вклада — 10 000 ₽. " }, { t: "Часть условий не подтверждена документами — уточните у специалиста банка.", good: true }],
    status: "NEEDS_REVIEW",
  },
];

const STEPS = ["Ответ AI", "Проверка по источникам", "Итоговый ответ"];

export function HeroDemo() {
  const reduce = useReducedMotion();
  const [ex, setEx] = useState(0);
  const [step, setStep] = useState(0);
  const [auto, setAuto] = useState(true);
  useEffect(() => {
    if (!auto || reduce) return;
    const t = setTimeout(() => {
      if (step < 2) setStep(step + 1);
      else { setStep(0); setEx((ex + 1) % EXAMPLES.length); }
    }, step === 2 ? 3600 : 2400);
    return () => clearTimeout(t);
  }, [step, ex, auto, reduce]);
  const e = EXAMPLES[ex];
  const choose = (i: number) => { setAuto(false); setEx(i); setStep(0); };

  return (
    <div className="relative overflow-hidden rounded-[28px] border hairline bg-white shadow-lift" aria-label="Демонстрация трансформации ответа">
      <div className="flex items-center justify-between gap-2 border-b hairline px-4 py-3">
        <div className="flex gap-1" role="tablist">
          {EXAMPLES.map((x, i) => (
            <button key={x.id} role="tab" aria-selected={i === ex} onClick={() => choose(i)}
              className={clsx("rounded-full px-3 py-1 text-[12px] font-medium transition-colors duration-200", i === ex ? "bg-ink-900 text-white" : "text-ink-600 hover:bg-ink-100")}>{x.tab}</button>
          ))}
        </div>
        <DemoBadge />
      </div>
      <div className="px-4 pt-4">
        <div className="label-mono mb-1">Вопрос клиента</div>
        <p className="text-[14px] font-medium text-ink-900">{e.question}</p>
      </div>
      <div className="flex items-center gap-1 px-4 pt-4">
        {STEPS.map((s, i) => (
          <button key={s} onClick={() => { setAuto(false); setStep(i); }} className="group flex flex-1 flex-col gap-1.5 text-left">
            <span className="h-1 overflow-hidden rounded-full bg-ink-100"><motion.span className="block h-full rounded-full bg-brand-600" initial={false} animate={{ width: i <= step ? "100%" : "0%" }} transition={{ duration: 0.6, ease: EASE }} /></span>
            <span className={clsx("text-[11px] font-medium", i === step ? "text-ink-900" : "text-ink-400 group-hover:text-ink-600")}>{String(i + 1).padStart(2, "0")} {s}</span>
          </button>
        ))}
      </div>
      <div className="min-h-[248px] p-4">
        <AnimatePresence mode="wait">
          <motion.div key={`${ex}-${step}`} initial={reduce ? false : { opacity: 0, y: 10, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0, y: -6, filter: "blur(4px)" }} transition={{ duration: 0.45, ease: EASE }}>
            {step === 0 && (
              <div className="rounded-2xl bg-ink-50 p-4 text-[14px] leading-relaxed text-ink-800">
                <div className="mb-2 flex items-center gap-1.5 text-[12px] text-ink-500"><Sparkles className="h-3.5 w-3.5" />Ответ языковой модели</div>
                {e.answer.map((p, i) => <span key={i} className={p.bad ? "rounded bg-bad-100 px-0.5 text-bad-700 underline decoration-bad-600/50 decoration-wavy underline-offset-4" : ""}>{p.t}</span>)}
              </div>
            )}
            {step === 1 && (
              <div className="space-y-2">
                {e.claims.map((c) => (
                  <div key={c.text} className="flex items-center justify-between gap-2 rounded-xl border hairline px-3 py-2 text-[13px]">
                    <span className="text-ink-800">{c.text}</span><Badge tone={c.tone} mono>{c.status}</Badge>
                  </div>
                ))}
                <div className="rounded-xl bg-brand-50 p-3">
                  <div className="mb-1 flex items-center gap-1.5 text-[12px] font-medium text-brand-800"><BookMarked className="h-3.5 w-3.5" />{e.source.title} · {e.source.ref}</div>
                  <p className="text-[13px] text-ink-700">«{e.source.quote}»</p>
                  {"note" in e.source && <p className="mt-1.5 text-[12px] font-medium text-warn-700">{(e.source as { note: string }).note}</p>}
                </div>
              </div>
            )}
            {step === 2 && (
              <div className="space-y-3">
                <div className="rounded-2xl bg-ok-50 p-4 text-[14px] leading-relaxed text-ink-900">
                  {e.final.map((p, i) => <span key={i} className={p.good ? "rounded bg-ok-100 px-0.5 text-ok-700" : ""}>{p.t}</span>)}
                </div>
                <div className="flex items-center gap-2 text-[12px] text-ink-600">
                  <CheckCircle2 className={clsx("h-4 w-4", e.status === "READY" ? "text-ok-600" : "text-warn-600")} />
                  <Badge tone={e.status === "READY" ? "ok" : "warn"} mono dot>{e.status.replace("_", " ")}</Badge>
                  {e.status === "READY" ? "исправлено по действующему тарифу" : "ставка не выдумана — ответ ушёл на проверку"}
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="flex items-center justify-between border-t hairline px-4 py-2.5 text-[12px] text-ink-500">
        <span>Иллюстрация на вымышленных данных демо-банка</span>
        <Link to={`/app/workspace?scenario=${e.id}`} className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">Запустить по-настоящему <ArrowRight className="h-3 w-3" /></Link>
      </div>
    </div>
  );
}
