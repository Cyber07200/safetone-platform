import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { api } from "../services/api";
import { useBank } from "../hooks/useBank";
import { useRun } from "../hooks/queries";
import { Card, ErrorState, PageHeader, SkeletonRows } from "../components/ui";
import { ResultView } from "../features/workspace/ResultView";
import { PipelineProgress } from "../features/workspace/PipelineProgress";
import { fmtDate } from "../lib/format";

export default function AuditPage() {
  const { id } = useParams();
  const { bankId } = useBank();
  const nav = useNavigate();
  const run = useRun(id);
  const rerun = useMutation({ mutationFn: () => api.rerun(bankId!, id!), onSuccess: (r) => nav(`/app/runs/${r.id}`) });

  return (
    <>
      <Link to="/app/history" className="mb-3 inline-flex items-center gap-1 text-[13px] text-ink-600 hover:text-ink-900"><ArrowLeft className="h-4 w-4" />История</Link>
      <PageHeader eyebrow="Audit Details" title="Аудит обработки" description={run.data ? <>ID <span className="font-mono text-[12px]">{run.data.id}</span> · {fmtDate(run.data.created_at, true)}{run.data.product_name ? ` · ${run.data.product_name}` : ""}</> : undefined} />
      {run.isLoading && <SkeletonRows rows={5} />}
      {run.isError && <ErrorState error={run.error} onRetry={() => run.refetch()} />}
      {rerun.isError && <ErrorState error={rerun.error} />}
      {run.data && (
        <div className="space-y-4">
          <Card className="p-4"><div className="label-mono mb-3">Pipeline</div><PipelineProgress stages={run.data.stages} layout="grid" /></Card>
          <div className="min-w-0">
            {run.data.execution_status === "completed" || run.data.execution_status === "failed"
              ? <ResultView run={run.data} onRerun={() => rerun.mutate()} rerunning={rerun.isPending} />
              : <Card className="p-6 text-[14px] text-ink-600">Обработка ещё выполняется…</Card>}
          </div>
        </div>
      )}
    </>
  );
}
