import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import clsx from "clsx";
import { ArrowUp, BookOpen, ChevronDown, ExternalLink, FileCheck2, FileText, ImageIcon, Lock, MessageSquarePlus, PanelLeft, Paperclip, Pencil, Trash2, X } from "lucide-react";
import { api, ApiError } from "../services/api";
import { useBank } from "../hooks/useBank";
import { useHealth } from "../hooks/queries";
import type { ChatAttachment, ChatConversation, ChatConversationDetail, ChatFinding, ChatMessage, ChatSource, Mode } from "../types/api";
import { Badge, ClaimBadge, EASE, ErrorState, Logo, Segmented, Skeleton, useDismiss } from "../components/ui";
import { fmtBytes, fmtDate } from "../lib/format";

const SUGGESTIONS = [
  "Сколько стоит снятие наличных с карты «Ясная» в чужом банкомате?",
  "Какая ставка по накопительному счёту «Прибой»?",
  "Может ли банк повысить ставку по кредиту в одностороннем порядке?",
  "Как подать жалобу и в какой срок банк ответит?",
];
const MAX_CHARS = 4000;
const MAX_FILE = 10 * 1024 * 1024;
const ACCEPT = ".pdf,.docx,.txt,.md,.html,.jpg,.jpeg,.png,image/jpeg,image/png";
const isImage = (name: string) => /\.(jpe?g|png)$/i.test(name);

/* ---------- tiny safe renderer for the model's markdown (no HTML injection) ---------- */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i} className="font-semibold text-ink-950">{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>);
}
function RichText({ text }: { text: string }) {
  const blocks = text.replace(/\r/g, "").split(/\n{2,}/);
  return (
    <div className="space-y-3">
      {blocks.map((b, i) => {
        const lines = b.split("\n").filter(Boolean);
        if (lines.length && lines.every((l) => /^\s*([-*•]|\d+[.)])\s+/.test(l))) {
          const ordered = /^\s*\d/.test(lines[0]);
          const Tag = ordered ? "ol" : "ul";
          return <Tag key={i} className={clsx("space-y-1.5 pl-5", ordered ? "list-decimal" : "list-disc", "marker:text-ink-400")}>
            {lines.map((l, k) => <li key={k}>{inline(l.replace(/^\s*([-*•]|\d+[.)])\s+/, ""))}</li>)}
          </Tag>;
        }
        if (/^#{1,4}\s/.test(b)) return <p key={i} className="font-semibold text-ink-950">{inline(b.replace(/^#{1,4}\s/, ""))}</p>;
        return <p key={i}>{lines.map((l, k) => <Fragment key={k}>{k > 0 && <br />}{inline(l)}</Fragment>)}</p>;
      })}
    </div>
  );
}

/* ---------- sources ---------- */
function Sources({ sources }: { sources: ChatSource[] }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) return null;
  return (
    <div className="mt-3">
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        className="inline-flex items-center gap-1.5 rounded-full bg-ink-50 px-3 py-1 text-[12px] font-medium text-ink-700 ring-1 ring-inset ring-black/[.05] transition-colors hover:bg-ink-100">
        <BookOpen className="h-3.5 w-3.5 text-brand-600" />Источники · {sources.length}
        <ChevronDown className={clsx("h-3.5 w-3.5 transition-transform duration-300 ease-apple", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.4, ease: EASE }} className="overflow-hidden">
            <ul className="stagger mt-2 space-y-2">
              {sources.map((s, i) => (
                <li key={i} className="rounded-xl border hairline bg-white p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium text-ink-900">{s.title}</div>
                      {s.section && <div className="mt-0.5 text-[12px] text-ink-500">{s.section}</div>}
                    </div>
                    {s.source_url && <a href={s.source_url} target="_blank" rel="noreferrer noopener" aria-label="Открыть источник" className="shrink-0 text-ink-400 hover:text-brand-600"><ExternalLink className="h-3.5 w-3.5" /></a>}
                  </div>
                  <p className="mt-1.5 line-clamp-4 text-[12px] leading-relaxed text-ink-600">{s.quote}</p>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ---------- messages ---------- */
type AttachmentLike = Pick<ChatAttachment, "filename" | "size"> & Partial<ChatAttachment>;

function AttachmentChip({ a, light }: { a: AttachmentLike; light?: boolean }) {
  const Icon = isImage(a.filename) ? ImageIcon : FileText;
  return (
    <div className={clsx("mt-2 flex items-center gap-2.5 rounded-2xl px-3 py-2 text-[12px]", light ? "bg-white/15 text-white" : "bg-ink-50 text-ink-700 ring-1 ring-inset ring-black/[.05]")}>
      <Icon className="h-4 w-4 shrink-0" />
      <div className="min-w-0">
        <div className="truncate font-medium">{a.filename}</div>
        <div className={light ? "text-white/75" : "text-ink-500"}>
          {fmtBytes(a.size)}{a.chars !== undefined && ` · ${a.chars.toLocaleString("ru-RU")} символов`}{a.recognized_by === "gigachat" && " · распознано GigaChat"}{a.truncated && " · проверено начало"}
        </div>
      </div>
    </div>
  );
}

function Findings({ items }: { items: ChatFinding[] }) {
  const [open, setOpen] = useState(true);
  const bad = items.filter((f) => f.status === "CONTRADICTED");
  const doubt = items.filter((f) => f.status !== "CONTRADICTED" && f.status !== "CONFIRMED");
  const ok = items.length - bad.length - doubt.length;
  const shown = [...bad, ...doubt];
  return (
    <div className="mt-4 overflow-hidden rounded-2xl border hairline">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full flex-wrap items-center gap-2 bg-ink-50/70 px-4 py-3 text-left">
        <FileCheck2 className="h-4 w-4 text-brand-600" />
        <span className="mr-auto text-[13px] font-semibold text-ink-900">Сверка с условиями банка и законами</span>
        <Badge tone="ok" dot>Подтверждено · {ok}</Badge>
        <Badge tone={bad.length ? "bad" : "muted"} dot>Расхождения · {bad.length}</Badge>
        <Badge tone={doubt.length ? "warn" : "muted"} dot>Уточнить · {doubt.length}</Badge>
      </button>
      <AnimatePresence initial={false}>
        {open && shown.length > 0 && (
          <motion.ul initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.4, ease: EASE }}
            className="divide-y divide-ink-100 overflow-hidden">
            {shown.map((f, i) => (
              <li key={i} className="px-4 py-3">
                <div className="flex items-start gap-2"><ClaimBadge status={f.status} /><p className="text-[13px] leading-relaxed text-ink-900">«{f.text}»</p></div>
                {f.source && <p className="mt-1.5 text-[12px] leading-relaxed text-ink-600"><span className="font-medium text-ink-800">{f.source}{f.section ? `, ${f.section}` : ""}:</span> {f.quote}</p>}
                {!f.source && <p className="mt-1.5 text-[12px] text-ink-500">{f.explanation}</p>}
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
      {items.length === 0 && <p className="px-4 py-3 text-[13px] text-ink-500">В документе нет утверждений с конкретными ставками, суммами или сроками.</p>}
    </div>
  );
}

type BubbleMessage = Pick<ChatMessage, "role" | "content" | "sources" | "mode"> & { attachment?: AttachmentLike | null; findings?: ChatFinding[] | null };

function Bubble({ m, fresh }: { m: BubbleMessage; fresh?: boolean }) {
  const reduce = useReducedMotion();
  const anim = fresh && !reduce ? { initial: { opacity: 0, y: 14, filter: "blur(4px)" }, animate: { opacity: 1, y: 0, filter: "blur(0px)" }, transition: { duration: 0.55, ease: EASE } } : {};
  if (m.role === "user") {
    return (
      <motion.div {...anim} className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-[22px] rounded-br-md bg-brand-600 px-4 py-2.5 text-[15px] leading-relaxed text-white shadow-[0_6px_20px_-10px_rgba(0,113,227,.7)]">
          {m.content}
          {m.attachment && <AttachmentChip a={m.attachment} light />}
        </div>
      </motion.div>
    );
  }
  return (
    <motion.div {...anim} className="flex gap-3">
      <div className="mt-0.5 shrink-0"><Logo compact /></div>
      <div className="min-w-0 flex-1 text-[15px] leading-relaxed text-ink-800">
        {m.mode === "demo" && <Badge tone="warn" mono className="mb-2">DEMO</Badge>}
        <RichText text={m.content} />
        {m.findings && <Findings items={m.findings} />}
        <Sources sources={m.sources} />
      </div>
    </motion.div>
  );
}

function Typing({ document }: { document?: boolean }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex items-center gap-3" role="status" aria-label="Ассистент печатает">
      <Logo compact />
      <div className="flex gap-1 rounded-full bg-ink-50 px-3.5 py-3">
        {[0, 1, 2].map((i) => <motion.span key={i} className="h-1.5 w-1.5 rounded-full bg-ink-400"
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }} transition={{ duration: 1, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }} />)}
      </div>
      <span className="text-[13px] text-ink-500">{document ? "Читаю документ и сверяю с условиями банка…" : "Ищу в правилах банка и законах…"}</span>
    </motion.div>
  );
}

/* ---------- conversation list ---------- */
function ConversationList({ items, activeId, onPick, onNew }: { items: ChatConversation[] | undefined; activeId?: string; onPick: () => void; onNew: () => void }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { bankId } = useBank();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const rename = useMutation({ mutationFn: ({ id, title }: { id: string; title: string }) => api.renameChat(id, title),
    onSuccess: () => { setEditing(null); qc.invalidateQueries({ queryKey: ["chats", bankId] }); } });
  const remove = useMutation({ mutationFn: (id: string) => api.deleteChat(id),
    onSuccess: (_, id) => { qc.invalidateQueries({ queryKey: ["chats", bankId] }); if (id === activeId) nav("/app/chat"); } });

  return (
    <div className="flex h-full flex-col">
      <button onClick={onNew} className="mb-3 flex items-center justify-center gap-2 rounded-full bg-ink-950 px-4 py-2.5 text-[14px] font-medium text-white transition-all duration-200 ease-apple hover:bg-ink-800 active:scale-[.98]">
        <MessageSquarePlus className="h-4 w-4" />Новый диалог
      </button>
      <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
        {!items && <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-11" />)}</div>}
        {items?.length === 0 && <p className="px-2 py-4 text-[13px] text-ink-500">Здесь появятся ваши диалоги.</p>}
        <ul className="space-y-0.5">
          <AnimatePresence initial={false}>
            {items?.map((c) => (
              <motion.li key={c.id} layout initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.35, ease: EASE }}>
                {editing === c.id ? (
                  <form onSubmit={(e) => { e.preventDefault(); if (draft.trim()) rename.mutate({ id: c.id, title: draft.trim() }); }} className="flex items-center gap-1 p-1">
                    <input autoFocus value={draft} maxLength={120} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setEditing(null)}
                      aria-label="Название диалога" className="field !py-1.5 !text-[13px]" />
                    <button type="button" aria-label="Отмена" onClick={() => setEditing(null)} className="grid h-8 w-8 shrink-0 place-items-center rounded-full hover:bg-ink-100"><X className="h-4 w-4" /></button>
                  </form>
                ) : (
                  <div className={clsx("group relative flex items-center rounded-xl transition-colors", c.id === activeId ? "bg-white shadow-card" : "hover:bg-white/70")}>
                    <Link to={`/app/chat/${c.id}`} onClick={onPick} className="min-w-0 flex-1 px-3 py-2.5">
                      <div className="truncate text-[13px] font-medium text-ink-900">{c.title}</div>
                      <div className="mt-0.5 text-[11px] text-ink-500">{fmtDate(c.updated_at, true)}</div>
                    </Link>
                    <div className="flex shrink-0 gap-0.5 pr-1.5 opacity-100 transition-opacity lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100">
                      <button aria-label="Переименовать" onClick={() => { setEditing(c.id); setDraft(c.title); }} className="grid h-7 w-7 place-items-center rounded-full text-ink-500 hover:bg-ink-100 hover:text-ink-900"><Pencil className="h-3.5 w-3.5" /></button>
                      <button aria-label="Удалить" onClick={() => { if (window.confirm(`Удалить диалог «${c.title}»?`)) remove.mutate(c.id); }} className="grid h-7 w-7 place-items-center rounded-full text-ink-500 hover:bg-bad-50 hover:text-bad-700"><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  </div>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
      <p className="mt-3 flex items-start gap-1.5 px-1 text-[11px] leading-relaxed text-ink-500"><Lock className="mt-0.5 h-3 w-3 shrink-0" />История шифруется (AES-256-GCM) и видна только в этом браузере.</p>
    </div>
  );
}

/* ---------- page ---------- */
export default function Chat() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { bankId, bank } = useBank();
  const health = useHealth();
  const reduce = useReducedMotion();
  const live = health.data?.live_available ?? false;
  const [mode, setMode] = useState<Mode>("live");
  const [text, setText] = useState("");
  const [pending, setPending] = useState<{ text: string; file: File | null } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [listOpen, setListOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useDismiss(listOpen, () => setListOpen(false));
  const knownLive = health.data?.live_available;
  useEffect(() => { if (knownLive !== undefined) setMode(knownLive ? "live" : "demo"); }, [knownLive]);

  const list = useQuery({ queryKey: ["chats", bankId], queryFn: () => api.chats(bankId!), enabled: !!bankId });
  const conv = useQuery({ queryKey: ["chat", id], queryFn: () => api.chat(id!), enabled: !!id });
  const send = useMutation({
    mutationFn: ({ text: content, file: f }: { text: string; file: File | null }) => {
      if (!f) return api.sendChat({ bank_id: bankId!, conversation_id: id ?? null, content, mode });
      const form = new FormData();
      form.append("bank_id", bankId!); form.append("content", content); form.append("mode", mode); form.append("file", f);
      if (id) form.append("conversation_id", id);
      return api.sendChatDocument(form);
    },
    onMutate: (v) => { setPending(v); setText(""); setFile(null); },
    onSuccess: (r) => {
      setFresh((s) => new Set(s).add(r.user_message.id).add(r.assistant_message.id));
      qc.setQueryData<ChatConversationDetail>(["chat", r.conversation.id], (old) => ({
        ...r.conversation, messages: [...(old?.messages ?? []), r.user_message, r.assistant_message] }));
      qc.invalidateQueries({ queryKey: ["chats", bankId] });
      if (r.conversation.id !== id) nav(`/app/chat/${r.conversation.id}`, { replace: !id });
    },
    onError: (_, v) => { setText(v.text); setFile(v.file); }, // keep the user's text and file so nothing is lost
    onSettled: () => { setPending(null); inputRef.current?.focus(); },
  });

  const messages = id ? conv.data?.messages ?? [] : [];
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "end" }); }, [messages.length, pending, reduce]);
  useEffect(() => { // auto-grow textarea
    const el = inputRef.current; if (!el) return;
    el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const submit = (value = text) => {
    const v = value.trim();
    if ((!v && !file) || send.isPending || !bankId || v.length > MAX_CHARS) return;
    send.mutate({ text: v, file });
  };
  const pick = (f: File | undefined | null) => {
    setFileError(null);
    if (!f) return;
    if (f.size > MAX_FILE) { setFileError("Файл больше 10 МБ."); return; }
    if (!/\.(pdf|docx|txt|md|html?|jpe?g|png)$/i.test(f.name)) { setFileError("Подходят PDF, Word (.docx), TXT, а также фото JPG и PNG."); return; }
    setFile(f);
    inputRef.current?.focus();
  };
  const startNew = () => { setListOpen(false); nav("/app/chat"); setText(""); inputRef.current?.focus(); };
  const empty = !id && !pending;
  const bankName = (bank?.name ?? "").replace(" (DEMO)", "").replace(/^Банк\s+/, "");
  const notFound = conv.error instanceof ApiError && conv.error.status === 404;

  return (
    <div className="-mb-6 flex h-[calc(100dvh-3.5rem-1.5rem)] gap-5 lg:-mb-8 lg:h-[calc(100dvh-3.5rem-2rem)]">
      {/* desktop list */}
      <aside className="hidden w-[260px] shrink-0 pb-6 lg:block"><ConversationList items={list.data} activeId={id} onPick={() => {}} onNew={startNew} /></aside>

      {/* mobile list drawer */}
      <AnimatePresence>
        {listOpen && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" onClick={() => setListOpen(false)} />
            <motion.div role="dialog" aria-modal="true" aria-label="Диалоги" initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }} transition={{ duration: 0.45, ease: EASE }}
              className="absolute inset-y-0 left-0 w-[300px] max-w-[85vw] bg-ink-50 p-4 shadow-lift">
              <ConversationList items={list.data} activeId={id} onPick={() => setListOpen(false)} onNew={startNew} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <section className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-t-[28px] border border-b-0 border-black/[.06] bg-white shadow-card"
        onDragOver={(e) => { if (e.dataTransfer.types.includes("Files")) { e.preventDefault(); setDragging(true); } }}
        onDragLeave={(e) => { if (e.currentTarget === e.target) setDragging(false); }}
        onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0]); }}>
        <AnimatePresence>
          {dragging && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="pointer-events-none absolute inset-3 z-20 grid place-items-center rounded-[24px] border-2 border-dashed border-brand-500 bg-brand-50/90 backdrop-blur-sm">
              <div className="text-center"><FileCheck2 className="mx-auto mb-2 h-8 w-8 text-brand-600" /><p className="text-[15px] font-semibold text-brand-800">Отпустите, чтобы проверить документ</p><p className="mt-1 text-[13px] text-brand-700">PDF, Word или фото</p></div>
            </motion.div>
          )}
        </AnimatePresence>
        <header className="flex items-center gap-2 border-b hairline px-4 py-3 sm:px-6">
          <button aria-label="Диалоги" onClick={() => setListOpen(true)} className="grid h-9 w-9 place-items-center rounded-full hover:bg-ink-100 lg:hidden"><PanelLeft className="h-5 w-5" /></button>
          <h1 className="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-[-0.01em] text-ink-950">{id ? conv.data?.title ?? " " : "Новый диалог"}</h1>
          <div className="w-[150px] shrink-0">
            <Segmented size="sm" ariaLabel="Режим чата" value={mode} onChange={setMode}
              options={[{ value: "live", label: "GigaChat", disabled: !live, title: live ? "Ответ языковой модели по законам из базы" : "GigaChat не подключён" }, { value: "demo", label: "Demo", title: "Без модели: показываю найденные нормы" }]} />
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto" aria-live="polite">
          <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
            {notFound && <ErrorState error={conv.error} />}
            {conv.isError && !notFound && <ErrorState error={conv.error} onRetry={() => conv.refetch()} />}
            {id && conv.isLoading && <div className="space-y-4"><Skeleton className="ml-auto h-12 w-2/3" /><Skeleton className="h-28 w-full" /></div>}

            {empty && (
              <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
                <motion.div initial={reduce ? false : { scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.8, ease: EASE }}
                  className="mb-5 grid h-16 w-16 place-items-center rounded-[22px] bg-gradient-to-b from-brand-500 to-brand-700 shadow-glow">
                  <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden><path d="M16 6l8 3v6c0 5-3.4 9.3-8 11-4.6-1.7-8-6-8-11V9l8-3z" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinejoin="round" /><path d="M12 16l3 3 5-6" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </motion.div>
                <motion.h2 initial={reduce ? false : { opacity: 0, y: 12, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} transition={{ duration: 0.8, delay: 0.1, ease: EASE }}
                  className="text-[28px] font-semibold tracking-[-0.03em] text-ink-950 sm:text-[34px]">Помощник банка {bankName}</motion.h2>
                <motion.p initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.25 }} className="mt-2 max-w-md text-[15px] text-ink-600">
                  Отвечает по тарифам и правилам банка и по законам РФ, помнит весь диалог и проверяет документы — PDF, Word или фото.
                </motion.p>
                <div className="mt-8 grid w-full gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((s, i) => (
                    <motion.button key={s} initial={reduce ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.35 + i * 0.07, ease: EASE }}
                      onClick={() => submit(s)} className="card card-hover p-4 text-left text-[14px] leading-snug text-ink-800">{s}</motion.button>
                  ))}
                  <motion.button initial={reduce ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.35 + SUGGESTIONS.length * 0.07, ease: EASE }}
                    onClick={() => fileRef.current?.click()} className="card card-hover flex items-center gap-3 border-dashed p-4 text-left sm:col-span-2">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600"><Paperclip className="h-5 w-5" /></span>
                    <span><span className="block text-[14px] font-medium text-ink-900">Проверить договор или выписку</span><span className="text-[13px] text-ink-500">Сверю условия с тарифами банка и законами. Можно перетащить файл сюда.</span></span>
                  </motion.button>
                </div>
              </div>
            )}

            <div className="space-y-7">
              {messages.map((m) => <Bubble key={m.id} m={m} fresh={fresh.has(m.id)} />)}
              {pending && <Bubble m={{ role: "user", content: pending.text || (pending.file ? `Проверь документ «${pending.file.name}»` : ""), sources: [], mode: null,
                attachment: pending.file ? { filename: pending.file.name, size: pending.file.size } : null }} fresh />}
              <AnimatePresence>{pending && <Typing document={!!pending.file} />}</AnimatePresence>
            </div>
            {send.isError && <div className="mt-4"><ErrorState error={send.error} /></div>}
            <div ref={endRef} />
          </div>
        </div>

        <div className="border-t hairline bg-white/80 px-4 pb-4 pt-3 backdrop-blur sm:px-6">
          <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="mx-auto max-w-3xl">
            <input ref={fileRef} type="file" accept={ACCEPT} className="hidden" aria-hidden tabIndex={-1}
              onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
            <AnimatePresence initial={false}>
              {file && (
                <motion.div initial={{ opacity: 0, y: 8, height: 0 }} animate={{ opacity: 1, y: 0, height: "auto" }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.3, ease: EASE }} className="overflow-hidden">
                  <div className="mb-2 flex max-w-sm items-center gap-2 rounded-2xl bg-ink-50 py-1.5 pl-3 pr-1.5 ring-1 ring-inset ring-black/[.05]">
                    {isImage(file.name) ? <ImageIcon className="h-4 w-4 shrink-0 text-brand-600" /> : <FileText className="h-4 w-4 shrink-0 text-brand-600" />}
                    <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-ink-800">{file.name}</span>
                    <span className="shrink-0 text-[12px] text-ink-500">{fmtBytes(file.size)}</span>
                    <button type="button" aria-label="Убрать файл" onClick={() => setFile(null)} className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-ink-500 hover:bg-ink-100"><X className="h-3.5 w-3.5" /></button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            {fileError && <p role="alert" className="mb-2 px-2 text-[12px] text-bad-700">{fileError}</p>}
            <div className="flex items-end gap-1.5 rounded-[24px] bg-ink-50 p-1.5 pl-1.5 ring-1 ring-inset ring-black/[.04] transition-shadow duration-300 focus-within:bg-white focus-within:ring-brand-500/40 focus-within:shadow-[0_0_0_4px_rgba(0,113,227,.12)]">
              <button type="button" aria-label="Прикрепить документ" title="PDF, Word или фото — до 10 МБ" onClick={() => fileRef.current?.click()} disabled={!bankId || send.isPending}
                className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900 disabled:opacity-40"><Paperclip className="h-5 w-5" /></button>
              <label htmlFor="chat-input" className="sr-only">Сообщение</label>
              <textarea id="chat-input" ref={inputRef} rows={1} value={text} onChange={(e) => setText(e.target.value)} disabled={!bankId}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}
                placeholder={file ? "Что проверить в документе? (необязательно)" : "Спросите о кредите, вкладе, карте…"}
                className="max-h-[200px] min-h-[24px] flex-1 resize-none bg-transparent py-2 text-[15px] leading-6 text-ink-900 placeholder:text-ink-400 focus:outline-none" />
              <motion.button type="submit" aria-label="Отправить" disabled={(!text.trim() && !file) || send.isPending || text.length > MAX_CHARS}
                whileTap={reduce ? undefined : { scale: 0.9 }}
                className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-600 text-white transition-all duration-200 ease-apple hover:bg-brand-500 disabled:bg-ink-200 disabled:text-ink-400">
                <ArrowUp className="h-5 w-5" strokeWidth={2.4} />
              </motion.button>
            </div>
            <div className="mt-2 flex justify-between gap-3 px-2 text-[11px] text-ink-500">
              <span>{file && isImage(file.name) ? "Фото распознаёт GigaChat; файл удаляется из GigaChat сразу после распознавания." : "Ответы основаны на правилах банка и законах и не заменяют консультацию юриста."}</span>
              {text.length > MAX_CHARS * 0.8 && <span className={clsx("shrink-0 tabular-nums", text.length > MAX_CHARS && "text-bad-700")}>{text.length}/{MAX_CHARS}</span>}
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
