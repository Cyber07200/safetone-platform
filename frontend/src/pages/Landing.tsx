import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { ArrowRight, Building2, ChevronDown, FileCheck2, GitBranch, Layers, Lock, Menu, Scale, ShieldCheck, SpellCheck2, Users, X } from "lucide-react";
import { Badge, Button, Logo, Reveal } from "../components/ui";
import { HeroDemo } from "../features/landing/HeroDemo";
import { DiffText } from "../features/workspace/DiffText";

const NAV = [["#how", "Как это работает"], ["#legal", "Legal Assurance"], ["#clarity", "Linguistic Clarity"], ["#security", "Безопасность"], ["#faq", "FAQ"]];

const PIPELINE = [
  { layer: "AI", title: "Генерация", text: "Готовая модель через API: YandexGPT, GigaChat или OpenAI-совместимая." },
  { layer: "Legal", title: "Утверждения", text: "Ответ разбирается на проверяемые факты: ставки, комиссии, сроки, обязательства." },
  { layer: "Legal", title: "Источники", text: "Поиск релевантных пунктов договоров, тарифов и нормативных документов банка." },
  { layer: "Legal", title: "Проверка", text: "Каждое утверждение сверяется с источником и получает статус и уровень риска." },
  { layer: "Legal", title: "Корректировка", text: "Ошибки исправляются только по источнику; без данных — осторожная формулировка." },
  { layer: "Clarity", title: "Понятный язык", text: "Канцелярит убирается, предложения короче, структура яснее." },
  { layer: "Clarity", title: "Проверка смысла", text: "Суммы, сроки, условия и оговорки должны сохраниться — иначе откат." },
  { layer: "Out", title: "Ответ + аудит", text: "READY, NEEDS REVIEW или FAILED — с полным журналом оснований." },
];

const STATUSES = [
  ["CONFIRMED", "ok", "Утверждение прямо подтверждено действующим источником"],
  ["CONTRADICTED", "bad", "Источник говорит иное — формулировка исправляется по источнику"],
  ["UNVERIFIED", "warn", "Данных нет — факт не выдумывается, ответ смягчается или идёт на проверку"],
  ["OUTDATED SOURCE", "warn", "Совпадает только с устаревшим или непроверенным документом"],
  ["NEEDS REVIEW", "warn", "Нужна экспертная юридическая оценка"],
] as const;

const RISKS = [
  ["LOW", "Проходит без лишних предупреждений"],
  ["MEDIUM", "Уточнение формулировки или осторожная оговорка"],
  ["HIGH", "Исправление по источнику или ручная проверка"],
  ["CRITICAL", "Безопасный черновик и обязательная ручная проверка"],
];

const ADVANTAGES = [
  ["Не блокирует безобидные ответы", "Нет списков «запрещённых слов». Термин «гарантия» или «без оплаты» не нарушение — нарушение только неподтверждённое утверждение."],
  ["Каждое исправление с основанием", "Документ, версия, пункт и цитата — для каждого изменения в ответе."],
  ["Честные статусы", "Если модель недоступна — FAILED, а не «успешно». Demo-сценарии помечены как демо, а не как генерация."],
  ["Несколько моделей", "Единый слой провайдеров, маршрутизация, повторы и fallback без привязки к одному вендору."],
  ["Версии и актуальность", "Дата загрузки ≠ дата действия. Устаревшие версии тарифов не подтверждают ответы."],
  ["Изоляция банков", "Документы, история и настройки каждого банка разделены на уровне данных."],
];

const TEAMS = [
  { icon: Scale, role: "Комплаенс и юристы", text: "Журнал решений с основаниями, очередь NEEDS REVIEW, контроль актуальности источников." },
  { icon: Layers, role: "Продуктовые команды", text: "Тарифы и договоры загружаются как источники — ответы ассистента сверяются с ними автоматически." },
  { icon: GitBranch, role: "IT и архитектура", text: "REST API с OpenAPI, модульный backend, PostgreSQL, конфигурация провайдеров через .env." },
  { icon: Users, role: "Клиентский сервис", text: "Понятные ответы без канцелярита — с сохранением всех условий и оговорок." },
];

const FAQ = [
  ["SafeTone — это своя нейросеть?", "Нет. SafeTone работает поверх готовых моделей через их API. Ценность — в проверке ответа по источникам, корректировке и аудите."],
  ["Проверяет ли SafeTone ответы по действующему законодательству?", "Только по тем источникам, которые загружены в базу знаний и имеют подтверждённую актуальность. В демо-версии законы представлены справочными пересказами без подтверждённой актуальности — утверждения, опирающиеся только на них, получают статус OUTDATED SOURCE."],
  ["Что происходит, если данных недостаточно?", "SafeTone не придумывает ставку или условие. Неподтверждённое существенное утверждение убирается, в аудите указывается, каких данных не хватает, а ответ переводится в NEEDS REVIEW."],
  ["Можно ли попробовать без API-ключей?", "Да. Demo Mode работает полностью локально: исходные ответы взяты из подготовленных сценариев (это явно отмечено), а юридический и лингвистический слои выполняются по-настоящему."],
  ["Передаются ли документы банка во внешние модели?", "По умолчанию — нет. Это отдельная настройка банка. Фрагменты, похожие на инструкции для модели (prompt injection), не передаются никогда."],
  ["SafeTone сертифицирован для банков?", "Нет. Это MVP. Сертификация и соответствие требованиям конкретного банка не заявляются и требуют отдельной работы."],
];

function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b hairline bg-white/85 backdrop-blur">
      <div className="container-page flex h-16 items-center gap-6">
        <Link to="/" aria-label="SafeTone — на главную"><Logo /></Link>
        <nav className="hidden items-center gap-5 md:flex" aria-label="Навигация">
          {NAV.map(([h, l]) => <a key={h} href={h} className="text-[14px] text-ink-600 transition-colors hover:text-ink-950">{l}</a>)}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Link to="/app" className="hidden sm:block"><Button variant="ghost" size="sm">Кабинет</Button></Link>
          <Link to="/app/workspace"><Button size="sm">Попробовать демо</Button></Link>
          <button className="rounded-md p-1.5 hover:bg-ink-100 md:hidden" aria-label="Меню" onClick={() => setOpen(!open)}>{open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
        </div>
      </div>
      {open && <nav className="container-page flex flex-col gap-1 pb-3 md:hidden">{NAV.map(([h, l]) => <a key={h} href={h} onClick={() => setOpen(false)} className="rounded-md px-2 py-2 text-[14px] text-ink-700 hover:bg-ink-50">{l}</a>)}</nav>}
    </header>
  );
}

function SectionHead({ eyebrow, title, text, id }: { eyebrow: string; title: string; text?: string; id?: string }) {
  return (
    <Reveal>
      <div id={id} className="max-w-2xl scroll-mt-24">
        <div className="label-mono mb-3 text-brand-700">{eyebrow}</div>
        <h2 className="text-[30px] font-semibold leading-[1.1] tracking-[-0.03em] text-ink-950 sm:text-[38px]">{title}</h2>
        {text && <p className="mt-4 text-[16px] leading-relaxed text-ink-600">{text}</p>}
      </div>
    </Reveal>
  );
}

export default function Landing() {
  const [faq, setFaq] = useState<number | null>(0);
  return (
    <div className="bg-white">
      <Header />
      {/* HERO */}
      <section className="relative overflow-hidden border-b hairline">
        <div className="grid-bg pointer-events-none absolute inset-0 [mask-image:linear-gradient(to_bottom,black,transparent_85%)]" />
        <div className="container-page relative grid items-center gap-12 py-14 lg:grid-cols-[1.05fr_1fr] lg:py-24">
          <Reveal>
            <Badge tone="info" className="mb-6">Legal & Linguistic Assurance для банковских AI-ассистентов</Badge>
            <h1 className="text-[40px] font-semibold leading-[1.02] tracking-[-0.04em] text-ink-950 sm:text-[56px] lg:text-[64px]">
              Юридическая точность.<br /><span className="text-brand-600">Понятный язык.</span><br />Доверие в каждом ответе.
            </h1>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-ink-600">
              SafeTone проверяет ответ языковой модели по договорам, тарифам и нормативным источникам банка, исправляет ошибки с указанием оснований и переписывает ответ понятно — не меняя юридический смысл.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/app/workspace"><Button size="lg" icon={<ArrowRight className="h-4 w-4" />} className="flex-row-reverse">Попробовать демо</Button></Link>
              <a href="#how"><Button size="lg" variant="secondary">Как это работает</Button></a>
            </div>
            <p className="mt-6 text-[13px] text-ink-500">Работает поверх YandexGPT, GigaChat и OpenAI-совместимых моделей · Demo Mode без API-ключей</p>
          </Reveal>
          <Reveal delay={0.1}><HeroDemo /></Reveal>
        </div>
      </section>

      {/* PIPELINE */}
      <section className="py-20 sm:py-28">
        <div className="container-page">
          <SectionHead id="how" eyebrow="Pipeline" title="Восемь этапов между моделью и клиентом" text="Каждый этап фиксирует статус, метод и результат. Если этап не выполнен — это видно в аудите, а не скрыто за «успешной» обработкой." />
          <Reveal className="mt-12">
            <ol className="grid gap-px overflow-hidden rounded-2xl border hairline bg-ink-200/70 sm:grid-cols-2 lg:grid-cols-4">
              {PIPELINE.map((p, i) => (
                <li key={p.title} className="group relative bg-white p-5 transition-colors hover:bg-brand-50/30">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[12px] text-ink-400">{String(i + 1).padStart(2, "0")}</span>
                    <span className={clsx("rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider",
                      p.layer === "Legal" ? "bg-brand-50 text-brand-700" : p.layer === "Clarity" ? "bg-ok-50 text-ok-700" : "bg-ink-100 text-ink-600")}>{p.layer}</span>
                  </div>
                  <div className="mt-6 text-[16px] font-semibold text-ink-950">{p.title}</div>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink-600">{p.text}</p>
                  {i < PIPELINE.length - 1 && <ArrowRight className="absolute right-3 top-1/2 hidden h-4 w-4 -translate-y-1/2 text-ink-300 lg:block" />}
                </li>
              ))}
            </ol>
          </Reveal>
        </div>
      </section>

      {/* LEGAL */}
      <section className="border-y hairline bg-ink-50/60 py-20 sm:py-28">
        <div className="container-page grid gap-12 lg:grid-cols-2">
          <div>
            <SectionHead id="legal" eyebrow="Legal Assurance Engine" title="Проверяются утверждения, а не слова" text="Юридический слой находит в ответе конкретные факты и сопоставляет их с пунктами действующих документов. Решение всегда соразмерно риску: подтверждённая часть сохраняется, проблемная — исправляется по источнику или уходит на проверку." />
            <Reveal className="mt-8">
              <ul className="space-y-2.5">
                {STATUSES.map(([s, tone, t]) => <li key={s} className="flex items-start gap-3"><Badge tone={tone} mono className="mt-0.5 w-[132px] justify-center">{s}</Badge><span className="text-[14px] leading-relaxed text-ink-700">{t}</span></li>)}
              </ul>
            </Reveal>
          </div>
          <Reveal delay={0.1}>
            <div className="card overflow-hidden">
              <div className="border-b hairline px-5 py-3"><span className="label-mono">Политика обработки рисков</span></div>
              <ul>{RISKS.map(([r, t], i) => (
                <li key={r} className="flex items-center gap-4 border-b hairline px-5 py-4 last:border-0">
                  <div className="flex w-24 gap-0.5">{[0, 1, 2, 3].map((k) => <span key={k} className={clsx("h-2 flex-1 rounded-sm", k <= i ? (i < 1 ? "bg-ok-600" : i < 2 ? "bg-warn-600" : "bg-bad-600") : "bg-ink-100")} />)}</div>
                  <span className="w-20 font-mono text-[12px] font-medium text-ink-900">{r}</span>
                  <span className="text-[14px] text-ink-700">{t}</span>
                </li>))}</ul>
              <div className="bg-ink-50/80 px-5 py-4 text-[13px] leading-relaxed text-ink-600">
                <FileCheck2 className="mb-2 h-5 w-5 text-brand-600" />
                Для каждого источника хранятся тип, банк и продукт, дата документа, дата вступления в силу, версия, статус актуальности, раздел и пункт.
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* CLARITY */}
      <section className="py-20 sm:py-28">
        <div className="container-page grid items-center gap-12 lg:grid-cols-[1fr_1.1fr]">
          <SectionHead id="clarity" eyebrow="Linguistic Clarity Engine" title="Понятно клиенту. Точно для юриста." text="После юридического слоя ответ переписывается простым языком в выбранном тоне. Затем SafeTone проверяет, что суммы, сроки, отрицания, условия и оговорки сохранились. Если смысл изменился — упрощение отклоняется." />
          <Reveal delay={0.1}>
            <div className="card p-5">
              <div className="label-mono mb-3">До → После · демо-сценарий «Закрытие счёта»</div>
              <DiffText before="В целях осуществления процедуры закрытия расчётного счёта Клиенту надлежит осуществить подачу заявления. Остаток денежных средств перечисляется не позднее 7 рабочих дней." after="Для закрытия расчётного счёта нужно подать заявление. Остаток денег перечисляется не позднее 7 рабочих дней." />
              <ul className="mt-5 grid gap-2 sm:grid-cols-2">
                {["Суммы, ставки и сроки сохранены", "Отрицания и запреты сохранены", "Условия и исключения сохранены", "Не добавлено новых обещаний"].map((c) => (
                  <li key={c} className="flex items-center gap-2 rounded-md bg-ok-50 px-3 py-2 text-[13px] text-ok-700"><ShieldCheck className="h-4 w-4" />{c}</li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap gap-1.5">{["Нейтральный банковский", "Дружелюбный", "Краткий и деловой", "Подробное объяснение"].map((t) => <Badge key={t}>{t}</Badge>)}</div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ADVANTAGES */}
      <section className="border-t hairline py-20 sm:py-28">
        <div className="container-page">
          <SectionHead eyebrow="Преимущества" title="Соразмерная проверка вместо слепой блокировки" />
          <Reveal className="mt-12">
            <div className="grid gap-px overflow-hidden rounded-2xl border hairline bg-ink-200/70 md:grid-cols-2 lg:grid-cols-3">
              {ADVANTAGES.map(([t, d], i) => (
                <div key={t} className="bg-white p-6"><span className="font-mono text-[12px] text-brand-600">{String(i + 1).padStart(2, "0")}</span><div className="mt-3 text-[16px] font-semibold text-ink-950">{t}</div><p className="mt-2 text-[14px] leading-relaxed text-ink-600">{d}</p></div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* TEAMS */}
      <section className="border-t hairline bg-ink-50/60 py-20 sm:py-28">
        <div className="container-page grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <SectionHead eyebrow="Для банковских команд" title="Один журнал решений для комплаенса, продукта и IT" text="SafeTone встраивается между AI-ассистентом и клиентом: ассистент продолжает работать, а каждое его утверждение получает проверяемое основание." />
          <div className="space-y-3">
            {TEAMS.map(({ icon: Icon, role, text }, i) => (
              <Reveal key={role} delay={i * 0.05}>
                <div className="card flex gap-4 p-5"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700"><Icon className="h-5 w-5" /></div>
                  <div><div className="text-[15px] font-semibold text-ink-950">{role}</div><p className="mt-1 text-[14px] leading-relaxed text-ink-600">{text}</p></div></div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* SECURITY */}
      <section className="bg-ink-950 py-20 text-white sm:py-28">
        <div className="container-page grid gap-12 lg:grid-cols-2">
          <Reveal>
            <div id="security" className="scroll-mt-24">
              <div className="label-mono mb-3 !text-brand-400">Безопасность и управление источниками</div>
              <h2 className="text-[30px] font-semibold leading-[1.1] tracking-[-0.03em] sm:text-[38px]">Данные банка остаются под контролем банка</h2>
              <p className="mt-4 text-[16px] leading-relaxed text-ink-300">Базовые механизмы безопасности MVP, спроектированные с учётом дальнейшего банковского внедрения. Соответствие конкретным регуляторным требованиям не заявляется и требует отдельной оценки.</p>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <ul className="grid gap-px overflow-hidden rounded-2xl bg-white/10 sm:grid-cols-2">
              {[[Lock, "Ключи только в backend", "API-ключи не попадают во frontend, историю и журналы; секреты маскируются."],
                [Building2, "Изоляция банков", "Банк видит только свои документы и общие нормативные источники."],
                [ShieldCheck, "Безопасная загрузка", "Проверка формата по содержимому, лимиты размера, защита от path traversal, код не исполняется."],
                [SpellCheck2, "Защита от prompt injection", "Инструкции системы отделены от данных; подозрительные фрагменты не передаются в модели."]].map(([Icon, t, d]) => {
                const I = Icon as typeof Lock;
                return <li key={t as string} className="bg-ink-950 p-6"><I className="h-5 w-5 text-brand-400" /><div className="mt-4 text-[15px] font-semibold">{t as string}</div><p className="mt-1.5 text-[14px] leading-relaxed text-ink-400">{d as string}</p></li>;
              })}
            </ul>
          </Reveal>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-20 sm:py-28">
        <div className="container-page grid gap-12 lg:grid-cols-[0.8fr_1.2fr]">
          <SectionHead id="faq" eyebrow="FAQ" title="Частые вопросы" />
          <div className="divide-y divide-ink-200 border-y hairline">
            {FAQ.map(([q, a], i) => (
              <div key={q}>
                <button className="flex w-full items-center justify-between gap-4 py-5 text-left" aria-expanded={faq === i} onClick={() => setFaq(faq === i ? null : i)}>
                  <span className="text-[16px] font-medium text-ink-950">{q}</span>
                  <ChevronDown className={clsx("h-5 w-5 shrink-0 text-ink-400 transition-transform", faq === i && "rotate-180")} />
                </button>
                {faq === i && <p className="-mt-1 pb-5 text-[15px] leading-relaxed text-ink-600">{a}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA + FOOTER */}
      <section className="border-t hairline">
        <div className="container-page flex flex-col items-start justify-between gap-6 py-16 md:flex-row md:items-center">
          <div><h2 className="text-[28px] font-semibold tracking-[-0.03em] text-ink-950">Посмотрите на реальную обработку</h2><p className="mt-2 text-[15px] text-ink-600">Десять демо-сценариев, полный аудит, без API-ключей.</p></div>
          <Link to="/app/workspace"><Button size="lg">Открыть AI Workspace</Button></Link>
        </div>
      </section>
      <footer className="border-t hairline bg-ink-50/60">
        <div className="container-page flex flex-col gap-6 py-10 text-[13px] text-ink-500 md:flex-row md:justify-between">
          <div className="max-w-md"><Logo /><p className="mt-3 leading-relaxed">SafeTone — MVP платформы проверки ответов AI. Не является юридической консультацией. Демонстрационный банк, его продукты, тарифы и договоры вымышлены.</p></div>
          <div className="flex gap-10">
            <div className="flex flex-col gap-2"><span className="label-mono">Продукт</span><Link to="/app/workspace" className="hover:text-ink-900">Workspace</Link><Link to="/app/knowledge" className="hover:text-ink-900">База знаний</Link><Link to="/app/history" className="hover:text-ink-900">История</Link></div>
            <div className="flex flex-col gap-2"><span className="label-mono">Разработчикам</span><a href="/docs" className="hover:text-ink-900">OpenAPI</a><Link to="/app/models" className="hover:text-ink-900">Провайдеры</Link></div>
          </div>
        </div>
      </footer>
    </div>
  );
}
