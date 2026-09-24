import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { useBank } from "./useBank";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
}
export function useProducts() {
  const { bankId } = useBank();
  return useQuery({ queryKey: ["products", bankId], queryFn: () => api.products(bankId!), enabled: !!bankId });
}
export function useScenarios() {
  const { bankId } = useBank();
  return useQuery({ queryKey: ["scenarios", bankId], queryFn: () => api.scenarios(bankId!), enabled: !!bankId });
}
export function useSettings() {
  const { bankId } = useBank();
  return useQuery({ queryKey: ["settings", bankId], queryFn: () => api.settings(bankId!), enabled: !!bankId });
}
export function useProviders() {
  return useQuery({ queryKey: ["providers"], queryFn: api.providers });
}
/** Polls the real processing state until the run finishes. */
export function useRun(id: string | null | undefined) {
  const { bankId } = useBank();
  return useQuery({
    queryKey: ["run", bankId, id],
    queryFn: () => api.run(bankId!, id!),
    enabled: !!bankId && !!id,
    refetchInterval: (q) => {
      const s = q.state.data?.execution_status;
      return s === "completed" || s === "failed" ? false : 400;
    },
  });
}
