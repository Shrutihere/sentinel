// Typed client for the Sentinel API.
const BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export type Decision = "allow" | "require_approval" | "deny";

export interface ToolCallResponse {
  decision: Decision;
  stage: string;
  reasons: string[];
  audit_id: number;
  executed: boolean;
  severity: string | null;
  score: number | null;
  status: string;
  approval_id: number | null;
}

export interface ActionPayload {
  agent_id: string;
  role?: string | null;
  tool: string;
  action: string;
  target: { system?: string; resource?: string | null; env?: string };
}

export interface ApprovalView {
  id: number;
  created_at: string;
  status: "pending" | "approved" | "denied";
  agent_id: string;
  role: string | null;
  tool: string;
  action: string;
  target: Record<string, unknown>;
  severity: string | null;
  score: number | null;
  reasons: string[];
  decided_at: string | null;
  decided_by: string | null;
  note: string | null;
  executed: boolean;
}

export interface AuditEntry {
  id: number;
  created_at: string;
  agent_id: string;
  role: string | null;
  tool: string;
  action: string;
  target: Record<string, unknown>;
  decision: Decision;
  stage: string;
  reasons: string[];
  executed: boolean;
  severity: string | null;
  score: number | null;
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  submit: (p: ActionPayload) =>
    fetch(`${BASE}/v1/tool-call`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(p),
    }).then((r) => j<ToolCallResponse>(r)),

  approvals: (status?: string) =>
    fetch(`${BASE}/v1/approvals${status ? `?status=${status}` : ""}`).then((r) =>
      j<ApprovalView[]>(r)
    ),

  decide: (id: number, action: "approve" | "deny", decided_by: string, note?: string) =>
    fetch(`${BASE}/v1/approvals/${id}/${action}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ decided_by, note }),
    }).then((r) => j<ApprovalView>(r)),

  audit: () => fetch(`${BASE}/v1/audit`).then((r) => j<AuditEntry[]>(r)),

  eval: () => fetch(`${BASE}/v1/eval/results`).then((r) => j<any>(r)),
};
