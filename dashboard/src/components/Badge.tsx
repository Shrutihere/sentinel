import type { ReactNode } from "react";

export function Badge({ kind, children }: { kind: string; children?: ReactNode }) {
  return <span className={`badge ${kind}`}>{children ?? kind.replace("_", " ")}</span>;
}

export function Sev({ severity, score }: { severity: string | null; score: number | null }) {
  if (!severity) return null;
  return (
    <span className="sev">
      severity <b>{severity}</b>
      {score != null ? ` · score ${score.toFixed(2)}` : ""}
    </span>
  );
}
