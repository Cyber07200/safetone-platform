import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ScanSearch } from "lucide-react";
import { api } from "../services/api";
import type { ProcessInput } from "../types/api";
import { useBank } from "../hooks/useBank";
import { useRun } from "../hooks/queries";
import { Badge, Card, EmptyState, ErrorState, PageHeader, ResultBadge, Skeleton } from "../components/ui";
import { ProcessForm } from "../features/workspace/ProcessForm";
import { PipelineProgress } from "../features/workspace/PipelineProgress";
import { ResultView } from "../features/workspace/ResultView";
import { fmtDate } from "../lib/format";

function RecentRuns() {
  const { bankId } = useBank();
  const q = useQuery({ queryKey: ["history", bankId, "recent"], queryFn: () => api.history({ bank_id: bankId, limit: 5 }), enabled: !!bankId });
  if (!q.data?.items.length) return null;
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between"><span className="label-mono">Недавние обработки</span><Link to="/app/history" className="text-[12px] font-medium text-brand-700 hover:underline">Вся история</Link></div>
      <ul className="divide-y divide-ink-100">
        {q.data.items.map((r) => (
          <li key={r.id}><Link to={`/app/runs/${r.id}`} className="flex items-center gap-3 py-2 text-[13px] hover:text-brand-700">
            <span className="flex-1 truncate">{r.question}</span><ResultBadge status={r.result_status} /><span className="hidden font-mono text-[11px] text-ink-400 sm:inline">{fmtDate(r.created_at, true)}</span>
          </Link></li>
        ))}
      </ul>
    </Card>
  );
}

export default function Workspace() {
  const [params] = useSearchParams();
  const { bankId } = useBank();
  const qc = useQueryClient();
  const [runId, setRunId] = useState<string | null>(null);
  const run = useRun(runId);

  const start = useMutation({
    mutationFn: (input: ProcessInput) => api.process(input),
    onSuccess: (r) => { setRunId(r.id); qc.setQueryData(["run", bankId, r.id], r); },
  });
  const rerun = useMutation({
    mutationFn: () => api.rerun(bankId!, runId!),
    onSuccess: (r) => { setRunId(r.id); qc.setQueryData(["run", bankId, r.id], r); },
  });
  const data = run.data;
  const finished = data && (data.execution_status === "completed" || data.execution_status === "failed");
  useEffect(() => {
    if (finished) {
      qc.invalidateQueries({ queryKey: ["history", bankId] });
      qc.invalidateQueries({ queryKey: ["stats", bankId] });
      if (window.innerWidth < 1024) document.getElementById("ws-result")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [finished, runId, bankId, qc]);

  return (
    <>
      <PageHeader eyebrow="AI Workspace" title="Проверка ответа AI"
        description="Вопрос → исходный ответ → проверка утверждений по источникам → юридическая корректировка → понятный язык → проверка сохранения смысла."
        actions={data?.mode === "demo" ? <Badge tone="warn" mono>DEMO MODE</Badge> : data?.mode === "live" ? <Badge tone="info" mono>LIVE</Badge> : undefined} />
      <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <Card className="p-4 sm:p-5">
            <ProcessForm onSubmit={(i) => start.mutate(i)} submitting={start.isPending || (!!runId && !finished)} initialScenario={params.get("scenario")} />
          </Card>
        </div>
        <div className="min-w-0 space-y-4">
          {start.isError && <ErrorState error={start.error} />}
          {rerun.isError && <ErrorState error={rerun.error} />}
          <Card className="scroll-mt-20 p-4" id="ws-result">
            <div className="mb-3 flex items-center justify-between"><span className="label-mono">Pipeline</span>{data && <span className="font-mono text-[11px] text-ink-400">{data.execution_status}</span>}</div>
            <PipelineProgress stages={data?.stages} layout="grid" />
          </Card>
          <div className="min-w-0">
            {!runId && !start.isPending && (
              <EmptyState icon={<ScanSearch className="h-5 w-5" />} title="Выберите сценарий и запустите проверку"
                description="Результат появится здесь: итоговый ответ, сравнение версий и подробный аудит каждого утверждения с источниками." />
            )}
            {(start.isPending || (runId && !data)) && <div className="space-y-3"><Skeleton className="h-16" /><Skeleton className="h-40" /><Skeleton className="h-24" /></div>}
            {run.isError && <ErrorState error={run.error} onRetry={() => run.refetch()} />}
            {data && !finished && <Card className="p-6 text-[14px] text-ink-600" aria-live="polite">Обработка выполняется… статус этапов обновляется в реальном времени.</Card>}
            {data && finished && <ResultView run={data} onRerun={() => rerun.mutate()} rerunning={rerun.isPending} />}
          </div>
          <RecentRuns />
          {!runId && <p className="flex items-center gap-1 text-[12px] text-ink-500">Демо-данные вымышлены и помечены DEMO. <Link to="/app/knowledge" className="inline-flex items-center gap-1 text-brand-700 hover:underline">Посмотреть источники <ArrowRight className="h-3 w-3" /></Link></p>}
        </div>
      </div>
    </>
  );
}
