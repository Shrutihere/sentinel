import { useEffect, useState } from "react";
import { api, type AuditEntry } from "../api";
import { Badge } from "./Badge";

export function Audit({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.audit().then(setRows).catch((e) => setErr(`Could not load audit (${e.message})`));
  }, [refreshKey]);

  return (
    <div className="card">
      <p className="section-title">Audit trail — every decision, append-only</p>
      {err && <p className="err">{err}</p>}
      {!err && rows.length === 0 && <p className="empty">No activity yet.</p>}
      {rows.map((e) => (
        <div className="audit-row" key={e.id}>
          <span className="small muted">{new Date(e.created_at).toLocaleTimeString()}</span>
          <div>
            <div className="mono small">{e.action}</div>
            <div className="stage">{e.stage} · {e.tool}{e.severity ? ` · ${e.severity}` : ""}</div>
          </div>
          <Badge kind={e.decision} />
        </div>
      ))}
    </div>
  );
}
