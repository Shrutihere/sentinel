import { useEffect, useState } from "react";
import { api, type ApprovalView } from "../api";
import { Badge, Sev } from "./Badge";

export function Approvals({ refreshKey, onChanged }: { refreshKey: number; onChanged: () => void }) {
  const [items, setItems] = useState<ApprovalView[]>([]);
  const [decidedBy, setDecidedBy] = useState("shruti");
  const [err, setErr] = useState("");
  const [showAll, setShowAll] = useState(false);

  async function load() {
    setErr("");
    try {
      setItems(await api.approvals(showAll ? undefined : "pending"));
    } catch (e: any) {
      setErr(`Could not load approvals (${e.message})`);
    }
  }
  useEffect(() => { load(); }, [refreshKey, showAll]);

  async function decide(id: number, action: "approve" | "deny") {
    await api.decide(id, action, decidedBy);
    await load();
    onChanged();
  }

  return (
    <div className="card">
      <div className="toolbar">
        <p className="section-title" style={{ margin: 0 }}>{showAll ? "All approval requests" : "Pending approvals"}</p>
        <div className="row" style={{ alignItems: "center" }}>
          <label style={{ margin: 0 }} className="small">decided by</label>
          <input style={{ width: 130 }} value={decidedBy} onChange={(e) => setDecidedBy(e.target.value)} />
          <button className="btn ghost" onClick={() => setShowAll(!showAll)}>{showAll ? "Show pending" : "Show all"}</button>
        </div>
      </div>

      {err && <p className="err">{err}</p>}
      {!err && items.length === 0 && (
        <p className="empty">No {showAll ? "" : "pending "}requests. Try the <b>Simulate</b> tab — submit a “deploy to prod” or “injection” action.</p>
      )}

      {items.map((a) => (
        <div className="item" key={a.id}>
          <div className="top">
            <span className="mono small muted">#{a.id} · {a.tool} · {String(a.target.env ?? "")}</span>
            <div className="row" style={{ alignItems: "center" }}>
              <Badge kind={a.status} />
              <Sev severity={a.severity} score={a.score} />
            </div>
          </div>
          <div className="action">{a.action}</div>
          <div className="reasons">{a.reasons[0]}</div>
          {a.status === "pending" ? (
            <div className="actions">
              <button className="btn approve" onClick={() => decide(a.id, "approve")}>Approve</button>
              <button className="btn deny" onClick={() => decide(a.id, "deny")}>Deny</button>
            </div>
          ) : (
            <p className="small muted" style={{ marginTop: 10 }}>
              {a.status} by <b>{a.decided_by}</b>{a.executed ? " · executed" : ""}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
