import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import type { Bank } from "../types/api";

interface BankCtx { bankId: string | null; bank: Bank | null; banks: Bank[]; setBankId: (id: string) => void; loading: boolean; error: unknown }
const Ctx = createContext<BankCtx | null>(null);
const KEY = "safetone.bank";

function readStored(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

export function BankProvider({ children }: { children: ReactNode }) {
  const q = useQuery({ queryKey: ["banks"], queryFn: api.banks });
  const [bankId, setBankIdState] = useState<string | null>(readStored);
  const banks = q.data ?? [];
  useEffect(() => {
    if (banks.length && (!bankId || !banks.some((b) => b.id === bankId))) setBankIdState(banks[0].id);
  }, [banks, bankId]);
  const setBankId = (id: string) => {
    setBankIdState(id);
    try { localStorage.setItem(KEY, id); } catch { /* ignore */ }
  };
  const bank = banks.find((b) => b.id === bankId) ?? null;
  return <Ctx.Provider value={{ bankId: bank?.id ?? null, bank, banks, setBankId, loading: q.isLoading, error: q.error }}>{children}</Ctx.Provider>;
}

export function useBank(): BankCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useBank outside BankProvider");
  return v;
}
