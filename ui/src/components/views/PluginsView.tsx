export default function PluginsView() {
  const COMING = [
    { name: "obsidian-importer", desc: "Importa vault Obsidian esistente nel brain locale" },
    { name: "calendar-sync", desc: "Sincronizza eventi calendario come thought nel COT" },
    { name: "telegram-bridge", desc: "Porta messaggi Telegram nel brain locale" },
    { name: "daily-note", desc: "Crea automaticamente una nota giornaliera" },
  ]

  return (
    <>
      <div className="view-header">
        <div className="view-header-left">
          <div className="view-title">Plugin</div>
          <div className="view-sub">Estendi il brain locale con plugin nativi Akaion</div>
        </div>
      </div>

      <div className="view-body">
        <div className="card mb-3" style={{ borderColor: "rgba(88,166,255,0.2)", background: "var(--accent-dim)" }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4, color: "var(--accent)" }}>
            Plugin system — in arrivo
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6 }}>
            Ogni plugin è un modulo Python installabile con <code style={{ background: "var(--bg-overlay)", padding: "1px 5px", borderRadius: 4 }}>akaion plugin install nome</code>.
            Può registrare nuovi tool, hook sugli eventi del brain, e comandi CLI.
          </div>
        </div>

        <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10 }}>Plugin in roadmap</div>
        {COMING.map((p) => (
          <div key={p.name} className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 500, marginBottom: 3 }}>{p.name}</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{p.desc}</div>
            </div>
            <span className="sync-pill local_only">soon</span>
          </div>
        ))}
      </div>
    </>
  )
}
