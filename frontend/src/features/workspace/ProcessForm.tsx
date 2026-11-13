import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Link } from "react-router-dom";
import { Play, FlaskConical, Radio } from "lucide-react";
import type { Mode, ProcessInput, Scenario, Tone } from "../../types/api";
import { useProducts, useProviders, useScenarios, useSettings } from "../../hooks/queries";
import { useBank } from "../../hooks/useBank";
import { Badge, Button, Field, Segmented, Skeleton, Toggle } from "../../components/ui";
import { TONES } from "../../lib/labels";

const CAT: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "info" | "muted" }> = {
  safe: { label: "безопасный", tone: "ok" }, contradiction: { label: "ошибка", tone: "bad" }, unverified: { label: "нет данных", tone: "warn" },
  legal: { label: "юр. вопрос", tone: "warn" }, critical: { label: "критично", tone: "bad" }, linguistic: { label: "язык", tone: "info" },
  outdated: { label: "актуальность", tone: "warn" },
};

export function ScenarioPicker({ scenarios, value, onChange }: { scenarios: Scenario[]; value: string | null; onChange: (s: Scenario) => void }) {
  return (
    <div className="grid gap-1.5" role="listbox" aria-label="Демо-сценарии">
      {scenarios.map((s, i) => (
        <button key={s.id} type="button" role="option" aria-selected={value === s.id} onClick={() => onChange(s)}
          className={clsx("group flex items-center gap-3 rounded-lg border px-3 py-2 text-left transition-all",
            value === s.id ? "border-brand-500 bg-brand-50/60 ring-2 ring-brand-100" : "hairline bg-white hover:border-ink-300")}>
          <span className="font-mono text-[11px] text-ink-400">{String(i + 1).padStart(2, "0")}</span>
          <span className="flex-1 text-[13px] font-medium text-ink-900">{s.title}</span>
          <Badge tone={CAT[s.category]?.tone ?? "muted"}>{CAT[s.category]?.label ?? s.category}</Badge>
        </button>
      ))}
    </div>
  );
}

export function ProcessForm({ onSubmit, submitting, initialScenario }: { onSubmit: (input: ProcessInput) => void; submitting: boolean; initialScenario?: string | null }) {
  const { bankId } = useBank();
  const products = useProducts();
  const scenarios = useScenarios();
  const providers = useProviders();
  const settings = useSettings();
  const liveAvailable = !!providers.data?.live_available;

  const [mode, setMode] = useState<Mode>("demo");
  const [source, setSource] = useState<"scenario" | "own">("scenario");
  const [scenarioId, setScenarioId] = useState<string | null>(initialScenario ?? null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [checkOwn, setCheckOwn] = useState(false);
  const [productId, setProductId] = useState<string>("");
  const [tone, setTone] = useState<Tone>("neutral");
  const [provider, setProvider] = useState("auto");

  useEffect(() => { if (settings.data) setTone(settings.data.bank.default_tone); }, [settings.data]);
  useEffect(() => { if (providers.isSuccess && !liveAvailable) setMode("demo"); }, [providers.isSuccess, liveAvailable]);
  useEffect(() => {
    if (!scenarios.data?.length) return;
    const s = scenarios.data.find((x) => x.id === (scenarioId ?? initialScenario)) ?? scenarios.data[0];
    pick(s);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarios.data]);

  const pick = (s: Scenario) => { setScenarioId(s.id); setQuestion(s.question); setProductId(s.product_id ?? ""); };
  const selected = useMemo(() => scenarios.data?.find((s) => s.id === scenarioId) ?? null, [scenarios.data, scenarioId]);
  const useScenario = mode === "demo" && source === "scenario";
  const needsAnswer = (mode === "demo" && source === "own") || (mode === "live" && checkOwn);

  const valid = !!bankId && (useScenario ? !!selected : question.trim().length >= 3 && (!needsAnswer || answer.trim().length >= 3));
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid || !bankId) return;
    onSubmit({
      bank_id: bankId, mode, tone,
      product_id: productId || null,
      question: useScenario ? selected!.question : question.trim(),
      scenario_id: useScenario ? selected!.id : null,
      answer_text: needsAnswer ? answer.trim() : null,
      provider: mode === "live" && !checkOwn ? provider : null,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-5" aria-label="Параметры проверки">
      <Field label="Режим AI">
        <Segmented ariaLabel="Режим AI" value={mode} onChange={setMode} options={[
          { value: "demo", label: <span className="inline-flex items-center gap-1.5"><FlaskConical className="h-3.5 w-3.5" />Demo</span> },
          { value: "live", label: <span className="inline-flex items-center gap-1.5"><Radio className="h-3.5 w-3.5" />Live AI</span>, disabled: !liveAvailable, title: liveAvailable ? "" : "AI-провайдеры не настроены" },
        ]} />
        {!liveAvailable && providers.isSuccess && (
          <p className="mt-1.5 text-[12px] text-ink-500">Live недоступен: ключи провайдеров не настроены. <Link to="/app/models" className="text-brand-700 hover:underline">Как подключить</Link></p>
        )}
        {mode === "demo" && <p className="mt-1.5 text-[12px] text-warn-700">Demo Mode: генерация моделью не выполняется. Юридическая и лингвистическая проверки работают по-настоящему на демо-базе знаний.</p>}
      </Field>

      {mode === "demo" && (
        <Segmented ariaLabel="Источник ответа" size="sm" value={source} onChange={setSource} options={[{ value: "scenario", label: "Готовый сценарий" }, { value: "own", label: "Проверить свой ответ AI" }]} />
      )}

      {useScenario ? (
        <div className="space-y-3">
          <div className="label-mono">Сценарий</div>
          {scenarios.isLoading ? <div className="space-y-1.5">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
            : scenarios.data ? <ScenarioPicker scenarios={scenarios.data} value={scenarioId} onChange={pick} /> : null}
          {selected && (
            <div className="rounded-lg border hairline bg-ink-50/70 p-3 text-[13px]">
              <div className="label-mono mb-1">Вопрос клиента</div>
              <p className="font-medium text-ink-900">{selected.question}</p>
              <p className="mt-2 text-[12px] leading-relaxed text-ink-600">{selected.demonstrates}</p>
            </div>
          )}
        </div>
      ) : (
        <>
          <Field label="Вопрос клиента" htmlFor="q">
            <textarea id="q" className="field min-h-[76px] resize-y" maxLength={2000} placeholder="Например: какая комиссия за снятие наличных с кредитной карты?" value={question} onChange={(e) => setQuestion(e.target.value)} />
          </Field>
          <Field label="Продукт банка" htmlFor="product">
            <select id="product" className="field" value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">Все продукты банка</option>
              {products.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
          {mode === "live" && (
            <>
              <div className="flex items-center justify-between gap-3">
                <label htmlFor="own" className="text-[13px] text-ink-800">Проверить готовый ответ вместо генерации</label>
                <Toggle id="own" checked={checkOwn} onChange={setCheckOwn} label="Проверить готовый ответ" />
              </div>
              {!checkOwn && (
                <Field label="Провайдер" htmlFor="prov" hint="auto — выбор по политике маршрутизации среди настроенных провайдеров">
                  <select id="prov" className="field" value={provider} onChange={(e) => setProvider(e.target.value)}>
                    <option value="auto">auto</option>
                    {providers.data?.providers.filter((p) => p.configured).map((p) => <option key={p.name} value={p.name}>{p.label} · {p.model}</option>)}
                  </select>
                </Field>
              )}
            </>
          )}
          {needsAnswer && (
            <Field label="Ответ AI для проверки" htmlFor="ans" hint="Вставьте ответ, сгенерированный вашей моделью. В аудите он будет помечен как «вставлено пользователем».">
              <textarea id="ans" className="field min-h-[120px] resize-y" maxLength={8000} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Процентная ставка по операциям покупок — 25% годовых…" />
            </Field>
          )}
        </>
      )}

      <Field label="Тон ответа" hint="Тон влияет только на подачу — юридические требования не меняются">
        <select className="field" aria-label="Тон ответа" value={tone} onChange={(e) => setTone(e.target.value as Tone)}>
          {Object.entries(TONES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </Field>

      <Button type="submit" size="lg" className="w-full" loading={submitting} disabled={!valid} icon={<Play className="h-4 w-4" />}>
        Запустить проверку
      </Button>
    </form>
  );
}
