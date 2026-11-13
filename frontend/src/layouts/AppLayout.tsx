import { useCallback, useState } from "react";
import { NavLink, Outlet, useLocation, Link } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import clsx from "clsx";
import { BookOpen, Cpu, History, LayoutGrid, Menu, MessagesSquare, Settings, Sparkles, X } from "lucide-react";
import { Badge, DemoBadge, EASE, Logo, useDismiss } from "../components/ui";
import { useBank } from "../hooks/useBank";
import { useHealth } from "../hooks/queries";

const NAV = [
  { to: "/app", label: "Обзор", icon: LayoutGrid, end: true },
  { to: "/app/chat", label: "Ассистент", icon: MessagesSquare },
  { to: "/app/workspace", label: "AI Workspace", icon: Sparkles },
  { to: "/app/history", label: "История", icon: History },
  { to: "/app/knowledge", label: "База знаний", icon: BookOpen },
  { to: "/app/models", label: "GigaChat", icon: Cpu },
  { to: "/app/settings", label: "Настройки", icon: Settings },
];

function Nav({ onNavigate, id }: { onNavigate?: () => void; id: string }) {
  return (
    <nav className="flex flex-col gap-0.5" aria-label="Разделы">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => clsx("group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-[14px] font-medium transition-colors duration-200",
            isActive ? "text-ink-950" : "text-ink-600 hover:bg-ink-50 hover:text-ink-900")}>
          {({ isActive }) => (<>
            {/* Active pill glides between items instead of jumping. */}
            {isActive && <motion.span layoutId={`nav-pill-${id}`} className="absolute inset-0 rounded-xl bg-ink-100/80" transition={{ type: "spring", stiffness: 420, damping: 36 }} />}
            <Icon className={clsx("relative h-4 w-4 transition-transform duration-300 ease-apple motion-safe:group-hover:scale-110", isActive ? "text-brand-600" : "text-ink-400 group-hover:text-ink-600")} />
            <span className="relative">{label}</span>
          </>)}
        </NavLink>
      ))}
    </nav>
  );
}

function BankSwitcher() {
  const { banks, bankId, setBankId, bank } = useBank();
  if (banks.length <= 1) {  // one bank installed: nothing to choose
    return (
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate text-[14px] font-semibold tracking-[-0.01em] text-ink-900">{bank?.name.replace(" (DEMO)", "") ?? ""}</span>
        {bank?.is_demo && <DemoBadge />}
      </div>
    );
  }
  return (
    <div className="flex min-w-0 items-center gap-2">
      <label htmlFor="bank" className="sr-only">Банк</label>
      <select id="bank" value={bankId ?? ""} onChange={(e) => setBankId(e.target.value)}
        className="h-9 w-full min-w-0 max-w-[240px] truncate rounded-full border-0 bg-ink-50 pl-4 pr-8 text-[13px] font-medium text-ink-800 hover:bg-ink-100 focus:outline-none focus:ring-4 focus:ring-brand-100">
        {banks.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
      </select>
      {bank?.is_demo && <DemoBadge className="hidden sm:inline-flex" />}
    </div>
  );
}

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const health = useHealth();
  const reduce = useReducedMotion();
  const live = health.data?.live_available;
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close);

  return (
    <div className="min-h-screen bg-ink-50">
      <aside className="glass fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r hairline px-3 py-4 lg:flex">
        <Link to="/" className="mb-6 px-2"><Logo /></Link>
        <Nav id="side" />
        <div className="mt-auto rounded-2xl bg-ink-50 p-3.5 text-[12px] leading-relaxed text-ink-600">
          <div className="label-mono mb-1">Принцип</div>
          Юридическая точность. Понятный язык. Доверие в каждом ответе.
        </div>
      </aside>

      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" onClick={close} />
            <motion.aside role="dialog" aria-modal="true" aria-label="Меню" initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }} transition={{ duration: 0.45, ease: EASE }}
              className="absolute inset-y-0 left-0 w-72 bg-white px-3 py-4 shadow-lift">
              <div className="mb-6 flex items-center justify-between px-2">
                <Logo />
                <button aria-label="Закрыть меню" autoFocus onClick={close} className="grid h-8 w-8 place-items-center rounded-full bg-ink-50 hover:bg-ink-100"><X className="h-4 w-4" /></button>
              </div>
              <Nav id="drawer" onNavigate={close} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="lg:pl-60">
        <header className="glass sticky top-0 z-20 flex h-14 items-center gap-3 border-b hairline px-4 sm:px-6">
          <button aria-label="Открыть меню" aria-expanded={open} onClick={() => setOpen(true)} className="grid h-9 w-9 place-items-center rounded-full hover:bg-ink-100 lg:hidden"><Menu className="h-5 w-5" /></button>
          <BankSwitcher />
          <div className="ml-auto flex shrink-0 items-center gap-2">
            {health.isError ? <Badge tone="bad" dot>API недоступен</Badge> :
              live === undefined ? null : live
                ? <Badge tone="ok" dot title="Настроен хотя бы один AI-провайдер"><span className="hidden sm:inline">Live AI доступен</span><span className="sm:hidden">Live</span></Badge>
                : <Link to="/app/models"><Badge tone="muted" dot title="Ключи AI-провайдеров не настроены"><span className="hidden sm:inline">Live AI не подключён · работает Demo</span><span className="sm:hidden">Demo</span></Badge></Link>}
          </div>
        </header>
        <main className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <motion.div key={loc.pathname.split("/").slice(0, 3).join("/")} initial={reduce ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55, ease: EASE }} className="mx-auto max-w-[1280px]">
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}
