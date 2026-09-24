import { useState } from "react";
import { NavLink, Outlet, useLocation, Link } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import clsx from "clsx";
import { BookOpen, Cpu, History, LayoutGrid, Menu, Settings, Sparkles, X } from "lucide-react";
import { Badge, DemoBadge, Logo } from "../components/ui";
import { useBank } from "../hooks/useBank";
import { useHealth } from "../hooks/queries";

const NAV = [
  { to: "/app", label: "Обзор", icon: LayoutGrid, end: true },
  { to: "/app/workspace", label: "AI Workspace", icon: Sparkles },
  { to: "/app/history", label: "История", icon: History },
  { to: "/app/knowledge", label: "База знаний", icon: BookOpen },
  { to: "/app/models", label: "Модели", icon: Cpu },
  { to: "/app/settings", label: "Настройки", icon: Settings },
];

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5" aria-label="Разделы">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => clsx("group flex items-center gap-2.5 rounded-lg px-3 py-2 text-[14px] font-medium transition-colors",
            isActive ? "bg-brand-50 text-brand-800" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900")}>
          {({ isActive }) => (<>
            <Icon className={clsx("h-4 w-4", isActive ? "text-brand-600" : "text-ink-400 group-hover:text-ink-600")} />
            {label}
          </>)}
        </NavLink>
      ))}
    </nav>
  );
}

function BankSwitcher() {
  const { banks, bankId, setBankId, bank } = useBank();
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="bank" className="sr-only">Банк</label>
      <select id="bank" value={bankId ?? ""} onChange={(e) => setBankId(e.target.value)}
        className="h-9 max-w-[240px] truncate rounded-lg border border-ink-200 bg-white pl-3 pr-8 text-[13px] font-medium text-ink-800 focus:border-brand-500 focus:outline-none">
        {banks.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
      </select>
      {bank?.is_demo && <DemoBadge />}
    </div>
  );
}

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const health = useHealth();
  const reduce = useReducedMotion();
  const live = health.data?.live_available;

  return (
    <div className="min-h-screen bg-ink-50/60">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r hairline bg-white px-3 py-4 lg:flex">
        <Link to="/" className="mb-6 px-2"><Logo /></Link>
        <Nav />
        <div className="mt-auto rounded-lg border hairline bg-ink-50 p-3 text-[12px] leading-relaxed text-ink-600">
          <div className="label-mono mb-1">Принцип</div>
          Юридическая точность. Понятный язык. Доверие в каждом ответе.
        </div>
      </aside>

      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-ink-950/30" onClick={() => setOpen(false)} />
            <motion.aside initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }} transition={{ type: "tween", duration: 0.2 }}
              className="absolute inset-y-0 left-0 w-64 bg-white px-3 py-4 shadow-lift">
              <div className="mb-6 flex items-center justify-between px-2">
                <Logo />
                <button aria-label="Закрыть меню" onClick={() => setOpen(false)} className="rounded-md p-1.5 hover:bg-ink-100"><X className="h-5 w-5" /></button>
              </div>
              <Nav onNavigate={() => setOpen(false)} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b hairline bg-white/85 px-4 backdrop-blur sm:px-6">
          <button aria-label="Открыть меню" onClick={() => setOpen(true)} className="rounded-md p-1.5 hover:bg-ink-100 lg:hidden"><Menu className="h-5 w-5" /></button>
          <BankSwitcher />
          <div className="ml-auto flex items-center gap-2">
            {health.isError ? <Badge tone="bad" dot>API недоступен</Badge> :
              live === undefined ? null : live
                ? <Badge tone="ok" dot title="Настроен хотя бы один AI-провайдер"><span className="hidden sm:inline">Live AI доступен</span><span className="sm:hidden">Live</span></Badge>
                : <Link to="/app/models"><Badge tone="muted" dot title="Ключи AI-провайдеров не настроены"><span className="hidden sm:inline">Live AI не подключён · работает Demo</span><span className="sm:hidden">Demo</span></Badge></Link>}
          </div>
        </header>
        <main className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <motion.div key={loc.pathname} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="mx-auto max-w-[1280px]">
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}
