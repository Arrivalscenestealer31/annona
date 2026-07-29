export default function PluginsView() {
  const COMING = [
    { name: "obsidian-importer", desc: "Import an existing Obsidian vault into the local vault" },
    { name: "calendar-sync", desc: "Sync calendar events into the cloud as thoughts" },
    { name: "telegram-bridge", desc: "Bring Telegram messages into the local vault" },
    { name: "daily-note", desc: "Create a daily note automatically" },
  ]

  return (
    <>
      <div className="view-header">
        <div className="view-header-left">
          <div className="view-title">Plugin</div>
          <div className="view-sub">Extend the local vault with native Akaion plugins</div>
        </div>
      </div>

      <div className="view-body">
        <div className="card mb-3" style={{ borderColor: "rgba(88,166,255,0.2)", background: "var(--accent-dim)" }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4, color: "var(--accent)" }}>
            Plugin system — in arrivo
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6 }}>
            Every plugin is a Python module installable with <code style={{ background: "var(--bg-overlay)", padding: "1px 5px", borderRadius: 4 }}>akaion plugin install nome</code>.
            It can register new tools, hook into vault events, and add CLI commands.
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
