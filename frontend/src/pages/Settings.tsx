import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Save } from "lucide-react";
import { api } from "../services/api";
import { useBank } from "../hooks/useBank";
import { useProviders, useSettings } from "../hooks/queries";
import type { BankSettings } from "../types/api";
import { Button, Card, ErrorState, Field, PageHeader, SkeletonRows, Toggle } from "../components/ui";
import { TONES } from "../lib/labels";

export default function Settings() {
  const { bankId, bank } = useBank();
  const q = useSettings();
  const providers = useProviders();
  const qc = useQueryClient();
  const [form, setForm] = useState<BankSettings | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (q.data) setForm(q.data.bank); }, [q.data]);
  const save = useMutation({
    mutationFn: (data: Partial<BankSettings>) => api.saveSettings(bankId!, data),
    onSuccess: (r) => { qc.setQueryData(["settings", bankId], r); setSaved(true); setTimeout(() => setSaved(false), 1800); },
  });
  const set = <K extends keyof BankSettings>(k: K, v: BankSettings[K]) => form && setForm({ ...form, [k]: v });

  return (
    <>
      <PageHeader eyebrow="Settings" title="Настройки банка" description={`Параметры обработки для «${bank?.name ?? ""}». Настройки, история и документы каждого банка изолированы.`} />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isLoading && <SkeletonRows rows={4} />}
      {form && q.data && (
        <form onSubmit={(e) => { e.preventDefault(); const { bank_id: _b, ...rest } = form; void _b; save.mutate(rest); }} className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <Card className="space-y-5 p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Провайдер по умолчанию" htmlFor="dp" hint="Ручной выбор модели для Live Mode; auto — политика маршрутизации">
                <select id="dp" className="field" value={form.default_provider} onChange={(e) => set("default_provider", e.target.value)}>
                  <option value="auto">auto</option>
                  {providers.data?.providers.map((p) => <option key={p.name} value={p.name} disabled={!p.configured}>{p.label}{p.configured ? "" : " (не настроен)"}</option>)}
                </select>
              </Field>
              <Field label="Приоритет маршрутизации" htmlFor="qp">
                <select id="qp" className="field" value={form.quality_preference} onChange={(e) => set("quality_preference", e.target.value as BankSettings["quality_preference"])}>
                  <option value="economy">Экономия</option><option value="balanced">Баланс</option><option value="quality">Качество</option>
                </select>
              </Field>
              <Field label="Тон ответа по умолчанию" htmlFor="tn">
                <select id="tn" className="field" value={form.default_tone} onChange={(e) => set("default_tone", e.target.value as BankSettings["default_tone"])}>
                  {Object.entries(TONES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </Field>
              <Field label="Срок хранения истории, дней" htmlFor="rd" hint="Обработки старше срока удаляются при запуске сервера">
                <input id="rd" type="number" min={1} max={3650} className="field" value={form.retention_days} onChange={(e) => set("retention_days", Number(e.target.value))} />
              </Field>
            </div>
            <div className="flex items-start justify-between gap-4 rounded-lg border hairline p-4">
              <div>
                <label htmlFor="docs" className="text-[14px] font-medium text-ink-900">Передавать документы банка во внешние LLM</label>
                <p className="mt-1 text-[12px] leading-relaxed text-ink-600">По умолчанию выключено. Когда включено, фрагменты документов (кроме помеченных как подозрительные) передаются настроенному провайдеру как контекст генерации и LLM-верификации. Доказательная проверка работает локально в любом случае.</p>
              </div>
              <Toggle id="docs" checked={form.allow_documents_to_llm} onChange={(v) => set("allow_documents_to_llm", v)} label="Передавать документы во внешние LLM" />
            </div>
            {save.isError && <ErrorState error={save.error} />}
            <Button type="submit" loading={save.isPending} icon={saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}>{saved ? "Сохранено" : "Сохранить"}</Button>
          </Card>
          <Card className="h-fit p-5 text-[13px]">
            <div className="label-mono mb-3">Платформа</div>
            <dl className="space-y-2">
              {[["Режим по умолчанию", String(q.data.platform.default_mode).toUpperCase()], ["База данных", String(q.data.platform.database)],
                ["Макс. длина вопроса", `${q.data.platform.max_question_chars} симв.`], ["Макс. длина ответа", `${q.data.platform.max_answer_chars} симв.`],
                ["Макс. размер файла", `${q.data.platform.max_upload_mb} МБ`], ["Форматы", q.data.platform.allowed_formats.join(", ")],
                ["Тайм-аут AI", `${q.data.platform.ai_request_timeout_s} с`], ["Повторы AI", String(q.data.platform.ai_max_retries)]].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3"><dt className="text-ink-500">{k}</dt><dd className="text-right font-medium text-ink-800">{v}</dd></div>
              ))}
            </dl>
            <p className="mt-4 border-t hairline pt-3 text-[12px] leading-relaxed text-ink-500">API-ключи хранятся только в backend/.env и никогда не передаются во frontend, историю или журналы.</p>
          </Card>
        </form>
      )}
    </>
  );
}
