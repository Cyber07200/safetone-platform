import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { FileText, Globe2, ShieldAlert, Trash2, Upload, X } from "lucide-react";
import { api, ApiError } from "../services/api";
import { useBank } from "../hooks/useBank";
import { useProducts, useSettings } from "../hooks/queries";
import type { DocumentItem } from "../types/api";
import { ActualityBadge, Badge, Button, Card, DemoBadge, EASE, EmptyState, ErrorState, Field, PageHeader, SkeletonRows, useDismiss } from "../components/ui";
import { DOC_TYPES } from "../lib/labels";
import { fmtBytes, fmtDate } from "../lib/format";

function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  useDismiss(open, onClose);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" onClick={onClose} />
          <motion.aside role="dialog" aria-modal="true" aria-label={title} initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ duration: 0.5, ease: EASE }}
            className="absolute inset-y-0 right-0 flex w-full max-w-[560px] flex-col bg-white shadow-lift sm:inset-y-2 sm:right-2 sm:rounded-4xl">
            <div className="flex items-center justify-between border-b hairline px-6 py-4">
              <h2 className="text-[17px] font-semibold tracking-[-0.02em]">{title}</h2>
              <button onClick={onClose} aria-label="Закрыть" autoFocus className="grid h-8 w-8 place-items-center rounded-full bg-ink-50 text-ink-600 hover:bg-ink-100"><X className="h-4 w-4" /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">{children}</div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function UploadForm({ onDone }: { onDone: () => void }) {
  const { bankId } = useBank();
  const products = useProducts();
  const settings = useSettings();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [f, setF] = useState({ title: "", doc_type: "tariff", product_id: "", document_key: "", document_date: "", effective_from: "", effective_to: "", actuality_status: "unverified", actuality_note: "", source_url: "" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const maxMb = settings.data?.platform.max_upload_mb ?? 10;
  const tooBig = !!file && file.size > maxMb * 1024 * 1024;
  const up = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("bank_id", bankId!);
      form.append("file", file!);
      Object.entries(f).forEach(([k, v]) => { if (v) form.append(k, v); });
      return api.uploadDocument(form);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents", bankId] }); onDone(); },
  });
  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (file && f.title && !tooBig) up.mutate(); }}>
      <div onClick={() => fileRef.current?.click()} className="cursor-pointer rounded-xl2 border border-dashed border-ink-300 bg-ink-50/60 p-6 text-center hover:border-brand-400">
        <Upload className="mx-auto h-6 w-6 text-ink-400" />
        <div className="mt-2 text-[14px] font-medium text-ink-800">{file ? file.name : "Выберите файл"}</div>
        <div className="mt-0.5 text-[12px] text-ink-500">{file ? fmtBytes(file.size) : `PDF, DOCX, HTML, TXT, MD · до ${maxMb} МБ`}</div>
        <input ref={fileRef} type="file" className="hidden" accept=".pdf,.docx,.html,.htm,.txt,.md" aria-label="Файл документа"
          onChange={(e) => { const x = e.target.files?.[0] ?? null; setFile(x); if (x && !f.title) setF((p) => ({ ...p, title: x.name.replace(/\.[^.]+$/, "") })); }} />
      </div>
      {tooBig && <p className="text-[12px] text-bad-700">Файл больше {maxMb} МБ.</p>}
      <Field label="Название" htmlFor="t"><input id="t" className="field" value={f.title} onChange={set("title")} required /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Тип документа" htmlFor="dt"><select id="dt" className="field" value={f.doc_type} onChange={set("doc_type")}>{Object.entries(DOC_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Продукт" htmlFor="pr"><select id="pr" className="field" value={f.product_id} onChange={set("product_id")}><option value="">Все продукты банка</option>{products.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
        <Field label="Дата документа" htmlFor="dd"><input id="dd" type="date" className="field" value={f.document_date} onChange={set("document_date")} /></Field>
        <Field label="Статус актуальности" htmlFor="as" hint="Дата загрузки не считается датой актуальности"><select id="as" className="field" value={f.actuality_status} onChange={set("actuality_status")}>
          <option value="unverified">Не подтверждена</option><option value="current">Действующий</option><option value="superseded">Заменён</option><option value="expired">Утратил силу</option></select></Field>
        <Field label="Действует с" htmlFor="ef"><input id="ef" type="date" className="field" value={f.effective_from} onChange={set("effective_from")} /></Field>
        <Field label="Действует по" htmlFor="et"><input id="et" type="date" className="field" value={f.effective_to} onChange={set("effective_to")} /></Field>
      </div>
      <Field label="Ключ документа (для версий)" htmlFor="dk" hint="Одинаковый ключ = новая версия; действующая версия заменяет предыдущую"><input id="dk" className="field" value={f.document_key} onChange={set("document_key")} placeholder="card-tariffs" /></Field>
      <Field label="Ссылка на источник" htmlFor="su"><input id="su" type="url" className="field" value={f.source_url} onChange={set("source_url")} placeholder="https://" /></Field>
      <Field label="Комментарий об актуальности" htmlFor="an"><textarea id="an" className="field" rows={2} value={f.actuality_note} onChange={set("actuality_note")} /></Field>
      {up.isError && <ErrorState error={up.error} />}
      <Button type="submit" className="w-full" loading={up.isPending} disabled={!file || !f.title || tooBig} icon={<Upload className="h-4 w-4" />}>Загрузить и проиндексировать</Button>
    </form>
  );
}

function DocumentDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { bankId } = useBank();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["document", bankId, id], queryFn: () => api.document(bankId!, id) });
  const patch = useMutation({ mutationFn: (actuality_status: string) => api.patchDocument(bankId!, id, { actuality_status }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents", bankId] }); q.refetch(); } });
  const del = useMutation({ mutationFn: () => api.deleteDocument(bankId!, id), onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents", bankId] }); onClose(); } });
  const [confirm, setConfirm] = useState(false);
  if (q.isLoading) return <SkeletonRows />;
  if (q.isError) return <ErrorState error={q.error} />;
  const d = q.data!;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2"><Badge>{DOC_TYPES[d.doc_type]}</Badge><ActualityBadge a={d.effective_actuality} />{d.is_demo && <DemoBadge />}{d.is_global && <Badge tone="info">Общий источник</Badge>}<Badge mono>v{d.version}</Badge></div>
      <h3 className="text-[16px] font-semibold">{d.title}</h3>
      <dl className="grid grid-cols-2 gap-3 text-[13px]">
        <div><dt className="label-mono">Область</dt><dd>{d.scope_label || "—"}</dd></div>
        <div><dt className="label-mono">Продукт</dt><dd>{d.product_name ?? "Все продукты"}</dd></div>
        <div><dt className="label-mono">Дата документа</dt><dd>{fmtDate(d.document_date)}</dd></div>
        <div><dt className="label-mono">Действует</dt><dd>{d.effective_from ? `с ${fmtDate(d.effective_from)}` : "—"}{d.effective_to ? ` по ${fmtDate(d.effective_to)}` : ""}</dd></div>
        <div><dt className="label-mono">Загружен</dt><dd>{fmtDate(d.uploaded_at, true)}</dd></div>
        <div><dt className="label-mono">Файл</dt><dd className="break-all">{d.original_filename ?? "seed"} · {fmtBytes(d.size_bytes)}</dd></div>
      </dl>
      {d.actuality_note && <p className="rounded-md bg-ink-50 p-3 text-[13px] text-ink-700">{d.actuality_note}</p>}
      {d.security_flags.includes("prompt_injection_suspected") && <p className="flex gap-2 rounded-md bg-bad-50 p-3 text-[13px] text-bad-700"><ShieldAlert className="h-4 w-4 shrink-0" />В документе найдены фрагменты, похожие на инструкции для модели. Они помечены и не передаются во внешние LLM.</p>}
      {d.source_url && <a href={d.source_url} target="_blank" rel="noreferrer noopener" className="text-[13px] text-brand-700 hover:underline">{d.source_url}</a>}
      {!d.is_global && (
        <div className="flex flex-wrap items-center gap-2 border-y hairline py-3">
          <span className="label-mono mr-1">Актуальность</span>
          {(["current", "superseded", "expired", "unverified"] as const).map((s) => (
            <Button key={s} size="sm" variant={d.actuality_status === s ? "primary" : "secondary"} onClick={() => patch.mutate(s)} disabled={patch.isPending}>
              {{ current: "Действует", superseded: "Заменён", expired: "Утратил силу", unverified: "Не подтверждена" }[s]}
            </Button>
          ))}
        </div>
      )}
      <div>
        <div className="label-mono mb-2">Фрагменты · {d.chunks.length}</div>
        <ol className="space-y-2">{d.chunks.map((c) => (
          <li key={c.id} className={`rounded-md border p-3 text-[13px] leading-relaxed ${c.suspicious ? "border-bad-100 bg-bad-50" : "hairline"}`}>
            <div className="mb-1 font-mono text-[11px] text-ink-400">#{c.ordinal + 1}{c.section ? ` · ${c.section}` : ""}{c.page ? ` · стр. ${c.page}` : ""}{c.suspicious ? " · подозрение на prompt injection" : ""}</div>{c.text}
          </li>))}</ol>
      </div>
      {!d.is_global && (confirm
        ? <div className="flex gap-2"><Button variant="danger" onClick={() => del.mutate()} loading={del.isPending}>Удалить безвозвратно</Button><Button variant="secondary" onClick={() => setConfirm(false)}>Отмена</Button></div>
        : <Button variant="danger" icon={<Trash2 className="h-4 w-4" />} onClick={() => setConfirm(true)}>Удалить документ</Button>)}
      {(patch.error || del.error) && <ErrorState error={(patch.error || del.error) as ApiError} />}
    </div>
  );
}

function DocRow({ d, onOpen }: { d: DocumentItem; onOpen: (id: string) => void }) {
  return (
    <button onClick={() => onOpen(d.id)} className="flex w-full flex-wrap items-center gap-3 border-t hairline px-5 py-3.5 text-left transition-colors duration-200 first:border-t-0 hover:bg-ink-50">
      <FileText className="h-4 w-4 shrink-0 text-ink-400" />
      <span className="min-w-[12rem] flex-1"><span className="line-clamp-2 text-[14px] font-medium text-ink-900">{d.title}</span>
        <span className="block text-[12px] text-ink-500">{DOC_TYPES[d.doc_type]} · v{d.version} · {d.product_name ?? (d.is_global ? "все банки" : "все продукты")} · {d.chunk_count} фрагм.</span></span>
      {d.security_flags.length > 0 && <ShieldAlert className="h-4 w-4 text-bad-600" aria-label="Подозрение на prompt injection" />}
      {d.is_demo && <DemoBadge />}
      <ActualityBadge a={d.effective_actuality} />
    </button>
  );
}

export default function KnowledgeBase() {
  const { bankId } = useBank();
  const [type, setType] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["documents", bankId, type], queryFn: () => api.documents(bankId!, { doc_type: type }), enabled: !!bankId });
  const groups = useMemo(() => {
    const g: Record<string, DocumentItem[]> = { bank: [], global: [] };
    q.data?.forEach((d) => (d.is_global ? g.global : g.bank).push(d));
    return g;
  }, [q.data]);
  useEffect(() => { setSelected(null); }, [bankId]);
  const closeUpload = useCallback(() => setUploadOpen(false), []);
  const closeDetail = useCallback(() => setSelected(null), []);

  return (
    <>
      <PageHeader eyebrow="Knowledge Base" title="База знаний" description="Источники для доказательной проверки: договоры, тарифы, внутренние документы банка и общие нормативные источники. Статус актуальности определяется датами действия и версиями, а не датой загрузки."
        actions={<Button icon={<Upload className="h-4 w-4" />} onClick={() => setUploadOpen(true)}>Загрузить документ</Button>} />
      <div className="mb-5 flex flex-wrap gap-1.5" role="group" aria-label="Тип документа">
        {[["", "Все"], ...Object.entries(DOC_TYPES)].map(([k, v]) => (
          <button key={k} onClick={() => setType(k)} aria-pressed={type === k} className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors duration-200 ${type === k ? "bg-ink-900 text-white" : "bg-ink-50 text-ink-700 hover:bg-ink-100"}`}>{v}</button>
        ))}
      </div>
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isLoading && <SkeletonRows rows={6} />}
      {q.data && q.data.length === 0 && <EmptyState title="Документов нет" description="Загрузите договор или тариф, чтобы SafeTone мог проверять ответы по нему." action={<Button size="sm" onClick={() => setUploadOpen(true)}>Загрузить</Button>} />}
      {q.data && q.data.length > 0 && (
        <div className="space-y-6">
          {groups.bank.length > 0 && <div><div className="label-mono mb-2">Документы банка · {groups.bank.length}</div><Card className="overflow-hidden">{groups.bank.map((d) => <DocRow key={d.id} d={d} onOpen={setSelected} />)}</Card></div>}
          {groups.global.length > 0 && <div><div className="label-mono mb-2 flex items-center gap-1.5"><Globe2 className="h-3.5 w-3.5" />Общие нормативные источники · {groups.global.length}</div>
            <Card className="overflow-hidden">{groups.global.map((d) => <DocRow key={d.id} d={d} onOpen={setSelected} />)}</Card>
            <p className="mt-2 text-[12px] text-ink-500">Действующие тексты законов по данным справочной системы ГАРАНТ (дата редакции — в карточке закона). Официальный источник — pravo.gov.ru.</p></div>}
        </div>
      )}
      <Drawer open={uploadOpen} onClose={closeUpload} title="Загрузка документа"><UploadForm onDone={closeUpload} /></Drawer>
      <Drawer open={!!selected} onClose={closeDetail} title="Документ">{selected && <DocumentDetail id={selected} onClose={closeDetail} />}</Drawer>
    </>
  );
}
