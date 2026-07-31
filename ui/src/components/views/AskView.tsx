import { useEffect, useRef, useState } from "react"
import { kernel, AskResult, Decision, KernelError } from "../../api/kernel"

/**
 * Ask — the conversation, with the placement attached to every answer.
 *
 * This is the only screen where the product's claim is visible while it is
 * being made: you type a request, and what comes back is the answer *and* where
 * it was computed, under which rule, with everything the run refused to do. A
 * chat that returned only prose would be a worse version of every other chat.
 *
 * A held run is not an error state here. It renders as an answer of its own —
 * the substrate was not permitted, nothing left the machine, and that is the
 * outcome the operator is paying for.
 */

type Exchange = {
  id: number
  prompt: string
  result?: AskResult
  error?: string
  ms?: number
}

function classTone(klass?: string): string {
  if (klass === "restricted") return "var(--red)"
  if (klass === "internal") return "var(--yellow)"
  return "var(--text-muted)"
}

function Chip({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span className="an-chip">
      <span className="an-chip__k">{label}</span>
      <span className="an-chip__v" style={tone ? { color: tone } : undefined}>{value}</span>
    </span>
  )
}

function DecisionRow({ d }: { d: Decision }) {
  const held = d.outcome === "held" || d.outcome === "denied"
  return (
    <div className="an-decision">
      <span className={`an-decision__dot ${held ? "held" : ""}`} />
      <code className="an-decision__step">{d.step_id}</code>
      <span className="an-decision__kind">{d.kind}</span>
      <span className="an-decision__outcome" style={{ color: held ? "var(--red)" : "var(--green)" }}>
        {d.outcome}
      </span>
      <span className="an-decision__class" style={{ color: classTone(d.class) }}>{d.class}</span>
      <span className="an-decision__where">{d.substrate || "—"}</span>
      <span className="an-decision__why">
        {String(d.detail?.reason ?? d.rule_id ?? "")}
      </span>
    </div>
  )
}

function Answer({ x }: { x: Exchange }) {
  const [open, setOpen] = useState(false)
  const r = x.result

  if (x.error) {
    return (
      <div className="an-answer an-answer--error">
        <div className="an-answer__text">{x.error}</div>
      </div>
    )
  }
  if (!r) return <div className="an-answer an-answer--pending">Thinking…</div>

  const held = r.placement?.outcome === "held"
  const denied = r.tool_calls.filter((t) => t.error)

  return (
    <div className="an-answer">
      {held ? (
        <div className="an-held">
          <b>Held.</b> Nothing ran, and nothing left this machine.
          {r.placement?.reason ? <> {r.placement.reason}</> : null}
        </div>
      ) : (
        <div className="an-answer__text">{r.response || "(no answer)"}</div>
      )}

      <div className="an-answer__meta">
        {r.enforced && r.placement ? (
          <>
            <Chip label="class" value={r.placement.class} tone={classTone(r.placement.class)} />
            <Chip
              label="ran on"
              value={r.placement.substrate || "—"}
              tone={held ? "var(--red)" : "var(--green)"}
            />
          </>
        ) : (
          <Chip label="perimeter" value="not enforcing" tone="var(--yellow)" />
        )}
        <Chip label="turns" value={String(r.iterations)} />
        {x.ms !== undefined && <Chip label="took" value={`${(x.ms / 1000).toFixed(1)}s`} />}
        {denied.length > 0 && (
          <Chip label="refused" value={`${denied.length} tool call${denied.length > 1 ? "s" : ""}`} tone="var(--red)" />
        )}
        {r.decisions.length > 0 && (
          <button className="an-link" onClick={() => setOpen(!open)}>
            {open ? "hide" : "show"} {r.decisions.length} decision{r.decisions.length > 1 ? "s" : ""}
          </button>
        )}
      </div>

      {open && (
        <div className="an-decisions">
          {r.decisions.map((d) => <DecisionRow key={d.seq} d={d} />)}
        </div>
      )}
    </div>
  )
}

export default function AskView() {
  const [prompt, setPrompt] = useState("")
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState<Exchange[]>([])
  const [enforcing, setEnforcing] = useState<boolean | null>(null)
  const [policyNote, setPolicyNote] = useState("")
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    kernel.status()
      .then((s) => {
        setEnforcing(s.enforcing)
        setPolicyNote(s.enforcing ? `${s.substrates} substrates · ${s.rules} rules` : s.reason)
      })
      .catch(() => { setEnforcing(false); setPolicyNote("the daemon did not answer") })
  }, [])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }) }, [history, busy])

  const send = async () => {
    const text = prompt.trim()
    if (!text || busy) return
    const id = Date.now()
    setHistory((h) => [...h, { id, prompt: text }])
    setPrompt("")
    setBusy(true)
    const started = performance.now()
    try {
      const result = await kernel.ask(text)
      const ms = performance.now() - started
      setHistory((h) => h.map((x) => (x.id === id ? { ...x, result, ms } : x)))
    } catch (e) {
      const detail = e instanceof KernelError ? e.detail : String(e)
      setHistory((h) => h.map((x) => (x.id === id ? { ...x, error: detail } : x)))
    } finally {
      setBusy(false)
    }
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send() }
  }

  return (
    <>
      <div className="view-header">
        <div className="view-header-left">
          <div className="ak-view-title">Ask</div>
          <div className="ak-view-sub">
            {enforcing === null ? "…"
              : enforcing ? `Every turn is placed before it runs · ${policyNote}`
              : `No policy is enforcing — ${policyNote}`}
          </div>
        </div>
      </div>

      <div className="an-chat">
        <div className="an-chat__scroll">
          {history.length === 0 && (
            <div className="an-empty">
              <div className="an-empty__title">Ask it something.</div>
              <div className="an-empty__sub">
                Every answer carries where it ran and under which rule. Name a file and watch
                the class go up.
              </div>
            </div>
          )}

          {history.map((x) => (
            <div key={x.id} className="an-turn">
              <div className="an-prompt">{x.prompt}</div>
              <Answer x={x} />
            </div>
          ))}
          {busy && <div className="an-answer an-answer--pending">Placing and running…</div>}
          <div ref={endRef} />
        </div>

        <div className="an-composer">
          <textarea
            className="an-composer__input"
            placeholder="Ask the kernel… (Enter to send, Shift+Enter for a new line)"
            value={prompt}
            rows={2}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button className="ak-pill-cta" onClick={send} disabled={busy || !prompt.trim()}>
            {busy ? "Running…" : "Send"}
          </button>
        </div>
      </div>
    </>
  )
}
