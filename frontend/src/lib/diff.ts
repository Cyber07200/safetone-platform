export type DiffPart = { type: "same" | "add" | "del"; text: string };

const tokenize = (s: string) => s.match(/\s+|[^\s]+/g) ?? [];

/** Word-level LCS diff: highlights what the pipeline removed and added. */
export function diffWords(a: string, b: string): DiffPart[] {
  const x = tokenize(a), y = tokenize(b);
  const n = x.length, m = y.length;
  if (n * m > 400_000) return [{ type: "del", text: a }, { type: "add", text: b }];
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = x[i] === y[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: DiffPart[] = [];
  const push = (type: DiffPart["type"], text: string) => {
    const last = out[out.length - 1];
    if (last && last.type === type) last.text += text;
    else out.push({ type, text });
  };
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (x[i] === y[j]) { push("same", x[i]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { push("del", x[i]); i++; }
    else { push("add", y[j]); j++; }
  }
  while (i < n) push("del", x[i++]);
  while (j < m) push("add", y[j++]);
  // whitespace-only changes are not interesting
  return out.map((p) => (p.type !== "same" && !p.text.trim() ? { ...p, type: "same" as const } : p));
}
