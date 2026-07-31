// Client for the kernel's HTTP surface (runner/kernel_api.py).
//
// Kept apart from `runner.ts`, which talks to the vault and the sync engine:
// these are the routes that answer "where did this run, and why", and mixing
// them with note CRUD would bury the one part of the app that is the product.

const BASE = "http://localhost:7070/api/kernel"

export class KernelError extends Error {
  constructor(readonly status: number, readonly detail: string) {
    super(detail)
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    // FastAPI puts the useful sentence in `detail`; surfacing "422" alone would
    // hide the loader telling you exactly which line of the policy is wrong.
    let detail = `${res.status}`
    try {
      const body = await res.json()
      if (typeof body?.detail === "string") detail = body.detail
      else if (Array.isArray(body?.detail)) detail = body.detail.map((d: any) => d.msg).join("; ")
    } catch { /* body was not JSON */ }
    throw new KernelError(res.status, detail)
  }
  return res.json()
}

// ── Shapes ────────────────────────────────────────────────────────────────────

export interface KernelStatus {
  enforcing: boolean
  policy: string
  reason: string
  substrates?: number
  rules?: number
  default_class?: string
  decisions?: number
}

export interface PolicyClass {
  label: string
  paths: string[]
  patterns: string[]
  default: boolean
}

export interface PolicySubstrate {
  id: string
  kind: string
  jurisdiction: string
  max_class: string
  endpoint: string
  model: string
  tools: boolean
  vision: boolean
  distance: number
}

export interface PolicyRule {
  id: string
  class: string
  allow: string[]
  on_unavailable: string
  prefer: string
}

export interface PolicyDoc {
  source: string
  version: number
  default_class: string
  classes: PolicyClass[]
  substrates: PolicySubstrate[]
  rules: PolicyRule[]
  tools: { allow: Record<string, string[]>; deny_paths: string[] }
  skills: string[]
  redaction: { enabled: boolean; provider: string; endpoint: string }
}

export interface SubstrateHealth extends PolicySubstrate {
  up: boolean
  reason: string
  latency_ms: number | null
}

export interface Decision {
  seq: number
  ts: string
  run_id: string
  step_id: string
  kind: string
  outcome: string
  class: string
  substrate: string
  rule_id: string
  payload_digest: string
  detail: Record<string, any>
  hash: string
}

export interface AskResult {
  response: string
  iterations: number
  tool_calls: { tool: string; input: Record<string, any>; result: any; error: boolean }[]
  placement: { class: string; outcome: string; substrate: string; reason: string } | null
  enforced: boolean
  decisions: Decision[]
}

// ── Calls ─────────────────────────────────────────────────────────────────────

export const kernel = {
  status:     () => req<KernelStatus>("/status"),
  policy:     () => req<PolicyDoc>("/policy"),
  substrates: (probe = true) => req<{ probed: boolean; substrates: SubstrateHealth[] }>(
    `/substrates?probe=${probe}`,
  ),
  ledger:     (opts?: { limit?: number; held?: boolean; runId?: string }) => {
    const qs = new URLSearchParams()
    if (opts?.limit) qs.set("limit", String(opts.limit))
    if (opts?.held) qs.set("held", "true")
    if (opts?.runId) qs.set("run_id", opts.runId)
    const q = qs.toString()
    return req<{ path: string; total: number; shown?: number; entries: Decision[] }>(
      `/ledger${q ? `?${q}` : ""}`,
    )
  },
  verify:     () => req<{ path: string; ok: boolean; entries: number; problem: string; empty: boolean }>(
    "/ledger/verify",
  ),
  ask:        (prompt: string, maxIterations = 8) => req<AskResult>("/ask", {
    method: "POST",
    body: JSON.stringify({ prompt, max_iterations: maxIterations }),
  }),
}
