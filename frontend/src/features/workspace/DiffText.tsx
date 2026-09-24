import { useMemo } from "react";
import { diffWords } from "../../lib/diff";

/** Inline diff: removed fragments struck through in red, added in green. */
export function DiffText({ before, after, mode = "inline" }: { before: string; after: string; mode?: "inline" | "before" | "after" }) {
  const parts = useMemo(() => diffWords(before, after), [before, after]);
  return (
    <p className="whitespace-pre-line text-[14px] leading-relaxed text-ink-800">
      {parts.map((p, i) => {
        if (p.type === "same") return <span key={i}>{p.text}</span>;
        if (p.type === "del") return mode === "after" ? null : <del key={i} className="mark-del px-0.5">{p.text}</del>;
        return mode === "before" ? null : <ins key={i} className="mark-add px-0.5 no-underline">{p.text}</ins>;
      })}
    </p>
  );
}
