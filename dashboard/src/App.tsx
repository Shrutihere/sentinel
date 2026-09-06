import { useEffect, useState } from "react";
import { api } from "./api";
import { Simulate } from "./components/Simulate";
import { Approvals } from "./components/Approvals";
import { Audit } from "./components/Audit";
import { Evaluation } from "./components/Evaluation";

type Tab = "simulate" | "approvals" | "audit" | "eval";
const TABS: Tab[] = ["simulate", "approvals", "audit", "eval"];

export default function App() {
  const fromHash = location.hash.replace("#", "") as Tab;
  const [tab, setTab] = useState<Tab>(TABS.includes(fromHash) ? fromHash : "simulate");
  const [refreshKey, setRefreshKey] = useState(0);
  const [pending, setPending] = useState(0);

  const bump = () => setRefreshKey((k) => k + 1);
  const select = (t: Tab) => { setTab(t); location.hash = t; };

  // keep the pending badge fresh
  useEffect(() => {
    let alive = true;
    const poll = () => api.approvals("pending").then((a) => alive && setPending(a.length)).catch(() => {});
    poll();
    const t = setInterval(poll, 4000);
    return () => { alive = false; clearInterval(t); };
  }, [refreshKey]);

  return (
    <div className="app">
      <div className="header">
        <div>
          <div className="brand"><span className="shield">🛡</span> Sentinel</div>
        </div>
        <a href="https://github.com/Shrutihere/sentinel" target="_blank" rel="noreferrer">github.com/Shrutihere/sentinel ↗</a>
      </div>
      <p className="tagline">
        Risk-evaluation &amp; approval control plane for autonomous AI agents —
        every tool-call scored in context, high-risk actions held for a human.
      </p>

      <div className="tabs">
        <button className={`tab ${tab === "simulate" ? "active" : ""}`} onClick={() => select("simulate")}>Simulate</button>
        <button className={`tab ${tab === "approvals" ? "active" : ""}`} onClick={() => select("approvals")}>
          Approvals{pending > 0 && <span className="count">{pending}</span>}
        </button>
        <button className={`tab ${tab === "audit" ? "active" : ""}`} onClick={() => select("audit")}>Audit</button>
        <button className={`tab ${tab === "eval" ? "active" : ""}`} onClick={() => select("eval")}>Evaluation</button>
      </div>

      {tab === "simulate" && <Simulate onChanged={bump} />}
      {tab === "approvals" && <Approvals refreshKey={refreshKey} onChanged={bump} />}
      {tab === "audit" && <Audit refreshKey={refreshKey} />}
      {tab === "eval" && <Evaluation />}
    </div>
  );
}
