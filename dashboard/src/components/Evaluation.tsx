import { useEffect, useState } from "react";
import { api } from "../api";

const pct = (x: number | null) => (x == null ? "n/a" : `${(100 * x).toFixed(1)}%`);

export function Evaluation() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.eval().then(setData).catch((e) => setErr(e.message));
  }, []);

  if (err)
    return (
      <div className="card">
        <p className="empty">No eval results loaded.<br />
          <span className="small mono">run: uv run python -m sentinel.evaluate --provider gemini</span></p>
      </div>
    );
  if (!data) return <div className="card"><p className="empty">Loading…</p></div>;

  const m = data.metrics;
  return (
    <div>
      <div className="card">
        <p className="section-title">Benchmark — {m.n_total} labeled actions (safe · needs-approval · destructive · adversarial)</p>
        <div className="stats">
          <div className="stat"><div className="num good">{pct(m.destructive_catch_rate)}</div><div className="lbl">Destructive-catch rate</div></div>
          <div className="stat"><div className="num bad">{pct(m.false_approve_rate)}</div><div className="lbl">False-approve rate (unsafe allowed)</div></div>
          <div className="stat"><div className="num good">{pct(m.injection_catch_rate)}</div><div className="lbl">Injection catch (adversarial)</div></div>
          <div className="stat"><div className="num">{pct(m.exact_decision_accuracy)}</div><div className="lbl">Exact-decision accuracy</div></div>
          <div className="stat"><div className="num">{pct(m.false_block_rate)}</div><div className="lbl">False-block rate (safe blocked)</div></div>
          <div className="stat"><div className="num">{m.severity_mae?.toFixed(2)}</div><div className="lbl">Severity MAE (0–3 scale)</div></div>
        </div>
        {m.dangerous_misses?.length > 0 && (
          <p className="err">⚠ Dangerous misses: {m.dangerous_misses.join(", ")}</p>
        )}
      </div>

      <div className="card">
        <p className="section-title">Accuracy by category</p>
        <table>
          <thead><tr><th>Category</th><th>Cases</th><th>Exact accuracy</th></tr></thead>
          <tbody>
            {Object.entries(m.by_category).map(([c, cm]: any) => (
              <tr key={c}><td>{c}</td><td>{cm.n}</td><td>{pct(cm.exact_accuracy)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
