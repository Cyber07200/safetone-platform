import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import clsx from "clsx";
import { motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import type { Tone3 } from "../../lib/labels";
import { ACTUALITY, CLAIM, RESULT, RISK } from "../../lib/labels";
import type { Actuality, ClaimStatus, ResultStatus, Risk } from "../../types/api";
import { ApiError } from "../../services/api";

/* ---------- Button ---------- */
type Variant = "primary" | "secondary" | "ghost" | "danger";
interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> { variant?: Variant; size?: "sm" | "md" | "lg"; loading?: boolean; icon?: ReactNode }
export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest }, ref) {
  return (
    <button ref={ref} disabled={disabled || loading} className={clsx(
      "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[.98]",
      { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4 text-[14px]", lg: "h-12 px-5 text-[15px]" }[size],
      {
        primary: "bg-brand-600 text-white shadow-[0_1px_0_rgba(255,255,255,.15)_inset,0_1px_2px_rgba(10,42,140,.3)] hover:bg-brand-700",
        secondary: "border border-ink-200 bg-white text-ink-800 hover:border-ink-300 hover:bg-ink-50",
        ghost: "text-ink-700 hover:bg-ink-100",
        danger: "border border-bad-100 bg-bad-50 text-bad-700 hover:bg-bad-100",
      }[variant], className)} {...rest}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

/* ---------- Badges ---------- */
const toneCls: Record<Tone3, string> = {
  ok: "bg-ok-50 text-ok-700 ring-ok-600/20",
  warn: "bg-warn-50 text-warn-700 ring-warn-600/25",
  bad: "bg-bad-50 text-bad-700 ring-bad-600/20",
  info: "bg-brand-50 text-brand-700 ring-brand-600/20",
  muted: "bg-ink-50 text-ink-600 ring-ink-300/60",
};
const dotCls: Record<Tone3, string> = { ok: "bg-ok-600", warn: "bg-warn-600", bad: "bg-bad-600", info: "bg-brand-600", muted: "bg-ink-400" };

export function Badge({ tone = "muted", children, dot, mono, className, title }: { tone?: Tone3; children: ReactNode; dot?: boolean; mono?: boolean; className?: string; title?: string }) {
  return (
    <span title={title} className={clsx("inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[12px] font-medium ring-1 ring-inset", toneCls[tone], mono && "font-mono text-[11px] tracking-wide", className)}>
      {dot && <span className={clsx("h-1.5 w-1.5 rounded-full", dotCls[tone])} />}
      {children}
    </span>
  );
}
export const ResultBadge = ({ status }: { status: ResultStatus | null }) =>
  status ? <Badge tone={RESULT[status].tone} dot mono title={RESULT[status].hint}>{RESULT[status].label}</Badge> : <Badge mono>—</Badge>;
export const ClaimBadge = ({ status }: { status: ClaimStatus }) => <Badge tone={CLAIM[status].tone} mono title={CLAIM[status].ru}>{CLAIM[status].label}</Badge>;
export const RiskBadge = ({ risk }: { risk: Risk | null }) =>
  risk ? <Badge tone={RISK[risk].tone} mono title={`Риск: ${RISK[risk].ru}`}>{risk === "CRITICAL" ? "▲ " : ""}{RISK[risk].label}</Badge> : null;
export const ActualityBadge = ({ a }: { a: Actuality }) => <Badge tone={ACTUALITY[a].tone} dot>{ACTUALITY[a].label}</Badge>;
export const DemoBadge = ({ className }: { className?: string }) => <Badge tone="warn" mono className={className} title="Демонстрационные данные">DEMO</Badge>;

/* ---------- Layout bits ---------- */
export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("card", className)} {...rest}>{children}</div>;
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="label-mono mb-1.5">{eyebrow}</div>}
        <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-ink-950 sm:text-[28px]">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-ink-600">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, ariaLabel, size = "md" }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; disabled?: boolean; title?: string }[]; ariaLabel: string; size?: "sm" | "md" }) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="inline-flex w-full rounded-lg bg-ink-100 p-1">
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value} disabled={o.disabled} title={o.title}
          onClick={() => onChange(o.value)}
          className={clsx("relative flex-1 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
            size === "sm" ? "px-2 py-1 text-[12px]" : "px-3 py-1.5 text-[13px]",
            value === o.value ? "text-ink-950" : "text-ink-600 hover:text-ink-900")}>
          {value === o.value && <motion.span layoutId={`seg-${ariaLabel}`} className="absolute inset-0 rounded-md bg-white shadow-card" transition={{ type: "spring", stiffness: 500, damping: 38 }} />}
          <span className="relative">{o.label}</span>
        </button>
      ))}
    </div>
  );
}

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-[13px] font-medium text-ink-800">{label}</label>
      {children}
      {hint && <p className="mt-1 text-[12px] text-ink-500">{hint}</p>}
    </div>
  );
}

export function Toggle({ checked, onChange, label, id }: { checked: boolean; onChange: (v: boolean) => void; label: string; id?: string }) {
  return (
    <button id={id} type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
      className={clsx("relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors", checked ? "bg-brand-600" : "bg-ink-300")}>
      <span className={clsx("inline-block h-5 w-5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-5" : "translate-x-0.5")} />
    </button>
  );
}

/* ---------- States ---------- */
export const Skeleton = ({ className }: { className?: string }) => <div className={clsx("skeleton", className)} aria-hidden />;

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Загрузка">
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
    </div>
  );
}

export function EmptyState({ title, description, action, icon }: { title: string; description?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl2 border border-dashed border-ink-200 bg-ink-50/50 px-6 py-12 text-center">
      <div className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-white text-ink-400 shadow-card">{icon ?? <Inbox className="h-5 w-5" />}</div>
      <div className="text-[15px] font-semibold text-ink-900">{title}</div>
      {description && <p className="mt-1 max-w-md text-[13px] text-ink-600">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof ApiError ? error.message : "Не удалось загрузить данные.";
  const code = error instanceof ApiError ? error.code : null;
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl2 border border-bad-100 bg-bad-50 p-4">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-bad-600" />
      <div className="flex-1">
        <div className="text-[14px] font-medium text-bad-700">{msg}</div>
        {code && <div className="mt-0.5 font-mono text-[11px] text-bad-600/80">{code}</div>}
      </div>
      {onRetry && <Button size="sm" variant="secondary" icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={onRetry}>Повторить</Button>}
    </div>
  );
}

/* ---------- Motion ---------- */
export function FadeIn({ children, delay = 0, className, y = 8 }: { children: ReactNode; delay?: number; className?: string; y?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay, ease: [0.2, 0.7, 0.2, 1] }}>
      {children}
    </motion.div>
  );
}

export function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }} transition={{ duration: 0.5, delay, ease: [0.2, 0.7, 0.2, 1] }}>
      {children}
    </motion.div>
  );
}

/* ---------- Logo ---------- */
export function Logo({ className, compact }: { className?: string; compact?: boolean }) {
  return (
    <span className={clsx("inline-flex items-center gap-2", className)}>
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#1846D8" />
        <path d="M16 6l8 3v6c0 5-3.4 9.3-8 11-4.6-1.7-8-6-8-11V9l8-3z" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinejoin="round" />
        <path d="M12 16l3 3 5-6" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {!compact && <span className="text-[17px] font-semibold tracking-[-0.02em] text-ink-950">SafeTone</span>}
    </span>
  );
}
