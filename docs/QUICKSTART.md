# Akaion Runner - Guida Rapida

## 🚀 Quick Start

### 1. Installazione
```bash
./install.sh
```

Questo script:
- Verifica Python 3.10+
- Crea virtual environment
- Installa dipendenze
- Setup directories

### 2. Configurazione
```bash
# Autenticati con il tuo account Akaion
akaion login

# Configura permissions e preferenze
akaion init
```

### 3. Avvio
```bash
# Avvia il runner in modalità daemon
akaion run

# O usa lo script
./start.sh
```

## 📦 Build native app (.dmg / .msi / .AppImage)

L'app desktop è un **Tauri 2 shell** che incapsula il daemon Python come **sidecar PyInstaller**.

### Mac (.dmg)
```bash
# Prerequisiti
#   • Rust toolchain → https://rustup.rs
#   • Node 18+ (npm)
#   • Python venv già creato (./install.sh oppure ./start.sh una volta)

cd akaion-app-runner

# 1. Build sidecar Python (PyInstaller onefile)
./scripts/build-sidecar.sh
#   → produces ui/src-tauri/binaries/akaion-runner-<triple>

# 2. Build Tauri shell + bundle .dmg
cd ui
npm install
npm run tauri:build
#   → src-tauri/target/release/bundle/dmg/Akaion Runner_<ver>_<arch>.dmg
#   → src-tauri/target/release/bundle/macos/Akaion Runner.app
```

### Dev mode (hot-reload UI + sidecar real)
```bash
./start.sh --tauri-dev
```

### Windows / Linux
Build script + Tauri targets sono configurati. I bundle Win (`.exe` NSIS), Linux (`.AppImage` + `.deb`) e i due `.dmg` Mac vengono prodotti dal workflow GitHub Actions `release.yml`.

---

## 🚢 Cutting a release

Tutti i bundle cross-platform vengono compilati da `.github/workflows/release.yml`. Il workflow gira **solo** quando l'utente pusha un tag `v*` o lancia manualmente la action.

### 1. Bump version
Allinea la versione in TUTTI questi file (devono coincidere altrimenti i bundle hanno nomi inconsistenti):

- `ui/package.json` → `"version"`
- `ui/src-tauri/Cargo.toml` → `[package] version`
- `ui/src-tauri/tauri.conf.json` → `"version"`

> Nota: `runner/__init__.py` non espone `__version__` al momento, quindi non serve toccarlo.

### 2. Tag & push
```bash
git add ui/package.json ui/src-tauri/Cargo.toml ui/src-tauri/tauri.conf.json
git commit -m "release: v0.1.0"
git tag v0.1.0
git push origin main --tags
```

### 3. Cosa fa la CI
- Job `build` gira in parallelo su 4 runner: `macos-14` (M-series), `macos-13` (Intel), `windows-latest`, `ubuntu-22.04`.
- Ogni runner: setup Python 3.11 → setup Node 20 → setup Rust stable → build UI (`vite`) → PyInstaller (sidecar onefile) → `tauri build --target <triple>` → carica gli artifact (`.dmg` / `.exe` / `.msi` / `.AppImage` / `.deb`).
- Job `release` (solo su tag push): scarica tutti gli artifact, li appiattisce in `release-assets/` e crea una **GitHub Release DRAFT, prerelease=true**.

### 4. Review & publish
- Apri GitHub → Releases → la draft appena creata.
- Controlla che ci siano tutti gli asset attesi (5 file: 2× dmg, 1× exe, 1× AppImage, 1× deb — l'`.msi` Windows è opzionale).
- Quando sei pronto, premi **Publish release**.

### Manual build (smoke test — niente release)
- GitHub → Actions → workflow **release** → **Run workflow** → scegli il branch.
- Il job `release` viene saltato (è gated su `startsWith(github.ref, 'refs/tags/v')`).
- Scarica i bundle da **Actions → run → Artifacts** (retention 14 giorni).

### Tempi & costi
- Primo build (cache cargo vuota): ~25-35 min totali, dominati da macOS Apple Silicon.
- Build successivi (cache popolata): ~10-15 min.
- I runner macOS consumano minuti GitHub Actions a tariffa 10× rispetto a Linux. Evita di lanciare il workflow per ogni commit.

### Note di firma
Le build sono **unsigned**:
- macOS Gatekeeper: al primo lancio, right-click → Open.
- Windows SmartScreen: "More info" → "Run anyway".
- Linux: AppImage richiede `chmod +x`, `.deb` si installa con `sudo dpkg -i`.

Apple notarization e Windows EV cert sono pianificati per **Step 7c**; richiederanno secrets aggiuntivi nel repo (`APPLE_*`, `WINDOWS_CERTIFICATE_*`, `TAURI_SIGNING_PRIVATE_KEY`).

---

## 🔄 Auto-update

L'app, al lancio, fa un GET silenzioso al manifest GitHub
(`https://github.com/Akaion-repos/akaion-app-runner/releases/latest/download/latest.json`).
Se la versione nel manifest è > di quella installata, in cima alla finestra
compare un banner non-bloccante:

```
┌─────────────────────────────────────────────┐
│ ^ Akaion Runner 0.2.0 disponibile           │
│ [Aggiorna ora] [Dopo]                       │
└─────────────────────────────────────────────┘
```

- **Aggiorna ora**: il plugin Tauri scarica il bundle, verifica la firma
  contro la public key embedded nell'app, lo applica e fa relaunch.
- **Dopo**: dismiss locale per la sessione corrente. Riappare al prossimo avvio.
- Se non c'è rete o il manifest non risponde entro 10s → silenzio, nessun banner.
- In modalità web (`npm run dev` da browser) il banner non si mostra mai.

### First-time setup (publisher only)

L'auto-update **richiede una signing keypair Tauri** (separata da Apple/Windows code signing).
Una sola volta, prima del primo tag con auto-update attivo:

1. Genera le chiavi:
   ```bash
   ./scripts/generate-updater-keys.sh
   ```
   Lo script ti chiede una password (NON skippare) e scrive
   `~/.tauri/akaion-runner.key`. Stampa la **public key**.

2. Apri `ui/src-tauri/tauri.conf.json` → `plugins.updater.pubkey` e sostituisci
   `PLACEHOLDER_PUBLIC_KEY_GENERATED_BY_TAURI_SIGNER` con il valore stampato.
   Commit + push: ora le release verificano i bundle contro questa public key.

3. GitHub repo → Settings → Secrets and variables → Actions → New secret:
   - `TAURI_SIGNING_PRIVATE_KEY` = contenuto integrale del file `~/.tauri/akaion-runner.key`
   - `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` = la password che hai impostato

4. **Backup off-machine** del file `~/.tauri/akaion-runner.key`. Se lo perdi,
   ogni client già installato rifiuterà ogni futuro update (signature mismatch);
   l'unica soluzione sarebbe forzare i client a reinstallare manualmente.

5. (Opzionale ma consigliato) crea un file `SIGNING.md` locale — NON viene
   committato (è in `.gitignore`) — con location della key + password manager
   reference + data di rotazione, per il te del futuro.

6. Cut a release come da sezione **Cutting a release** (più sotto): la CI
   firma automaticamente ogni bundle e pubblica `latest.json` insieme ai `.dmg`/`.exe`/ecc.

### Che cosa pubblica la CI

Sotto `release-assets/` la action carica:
- `*.dmg` / `*.exe` / `*.AppImage` / `*.deb` (bundle utenti)
- `*.dmg.sig` / `*.exe.sig` / `*.AppImage.sig` (firme — necessarie al manifest)
- `latest.json` (consumato dal plugin updater client)

`.deb` non ha entry nel manifest: chi installa via apt aggiorna via apt.

---

## 🌐 Web UI

Il runner espone una UI web su `http://127.0.0.1:7070` (stesso processo, no Tauri).

- **Accesso**: apri `http://127.0.0.1:7070` dopo `./start.sh`.
- **Login**: Firebase (Google o Email/Password) usando il progetto prod.
- **Auto-build**: al primo `./start.sh` la UI viene buildata in `ui/dist/` (richiede Node 18+).
- **Rebuild manuale**: `cd ui && npm install && npm run build` — oppure `./start.sh --rebuild-ui`.

## 📝 Comandi Disponibili

### `akaion login`
Autentica il runner con il cloud Akaion.

```bash
# Interactive
akaion login

# Con API key
akaion login --api-key YOUR_API_KEY

# Custom URL
akaion login --url https://custom.akaion.com
```

### `akaion init`
Inizializza la configurazione.

```bash
# Interactive (recommended)
akaion init

# Non-interactive (usa defaults)
akaion init --no-interactive
```

### `akaion run`
Avvia il runner.

```bash
# Daemon mode (default)
akaion run

# Execute once e esci
akaion run --once

# Development mode (verbose)
akaion run --dev

# Execute specific task
akaion run --once --task "Analizza i file in ~/Documents"
```

### `akaion status`
Controlla lo stato del runner.

```bash
# Status summary
akaion status

# Verbose (mostra config)
akaion status --verbose
```

### `akaion logs`
Visualizza i logs.

```bash
# Ultime 50 righe
akaion logs

# Ultime 100 righe
akaion logs --tail 100

# Follow mode (real-time)
akaion logs --follow
```

### `akaion config`
Gestisci la configurazione.

```bash
# Mostra path config
akaion config

# Mostra contenuto
akaion config --show

# Edita
akaion config --edit

# Reset a default
akaion config --reset
```

### `akaion logout`
Rimuovi credenziali.

```bash
akaion logout
```

### `akaion version`
Mostra versione.

```bash
akaion version
```

## ⚙️ Configurazione

### File di Configurazione
`~/.akaion/config.yaml`

```yaml
# Cloud Backend
cloud:
  api_url: "https://api.akaion.com"
  polling_interval: 5
  timeout: 30

# AI Provider
ai:
  provider: "akaion"  # akaion | openai | anthropic | google | local
  model: "gpt-4"
  temperature: 0.7

# Permissions
permissions:
  filesystem:
    allowed_paths:
      - "~/Documents"
      - "~/Downloads"
    denied_paths:
      - "~/.ssh"
  
  shell:
    enabled: true
    allowed_commands:
      - "ls"
      - "cat"
      - "grep"

# Tools
tools:
  enabled:
    - filesystem
    - shell
    - browser
```

### Environment Variables

Crea `.env` nella directory del runner:

```bash
# Cloud
AKAION_API_KEY=your_api_key_here
AKAION_MAIN_URL=https://api.akaion.com
AKAION_AI_URL=https://ai.akaion.com
AKAION_CALENDAR_URL=https://calendar.akaion.com
AKAION_COT_URL=https://cot.akaion.com

# AI Providers (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
GOOGLE_API_KEY=...

# Development
AKAION_DEV_MODE=false
AKAION_LOG_LEVEL=INFO
```

## 🔐 Permissions

Il runner richiede permesso esplicito per:

### Filesystem
```yaml
permissions:
  filesystem:
    allowed_paths:
      - "~/Documents"      # Accesso a Documents
      - "~/work/project"   # Path specifico
    denied_paths:
      - "~/.ssh"           # Nega .ssh
      - "~/.*"             # Nega hidden files
    max_file_size_mb: 100
```

### Shell
```yaml
permissions:
  shell:
    enabled: true
    allowed_commands:
      - "ls"
      - "cat"
      - "git*"    # Wildcard: tutti i comandi git
    denied_commands:
      - "rm -rf"
      - "sudo"
```

### Network
```yaml
permissions:
  network:
    enabled: true
    allowed_domains:
      - "*.akaion.com"        # Tutti i subdomain
      - "api.openai.com"
      - "api.anthropic.com"
```

## 🤖 AI Providers

### Akaion AI (Default)
Usa il backend AI di Akaion - nessuna configurazione extra necessaria.

### OpenAI
```yaml
ai:
  provider: "openai"
  model: "gpt-4"
  openai:
    api_key: "sk-..."  # o usa OPENAI_API_KEY env var
```

### Anthropic (Claude)
```yaml
ai:
  provider: "anthropic"
  model: "claude-3-opus-20240229"
  anthropic:
    api_key: "sk-..."  # o usa ANTHROPIC_API_KEY env var
```

### Google (Gemini)
```yaml
ai:
  provider: "google"
  model: "gemini-pro"
  google:
    api_key: "..."  # o usa GOOGLE_API_KEY env var
```

### Local (Ollama)
```bash
# Installa Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Avvia un modello
ollama pull llama2
ollama serve
```

```yaml
ai:
  provider: "local"
  model: "llama2"
  local:
    endpoint: "http://localhost:11434"
```

## 📊 Monitoring

### Status Check
```bash
$ akaion status
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component         ┃ Status         ┃ Details                 ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Authentication    │ ✅ Authenticated│ runner-abc123           │
│ Configuration     │ ✅ Configured   │ ~/.akaion/config.yaml   │
│ Cloud Connection  │ ✅ Connected    │ https://api.akaion.com  │
└───────────────────┴────────────────┴─────────────────────────┘
```

### Logs
```bash
# Real-time monitoring
akaion logs --follow

# Filter by level (in log file)
grep "ERROR" logs/runner.log
grep "WARNING" logs/runner.log
```

## 🛠️ Troubleshooting

### Runner non si autentica
```bash
# Verifica credenziali
akaion status

# Re-login
akaion logout
akaion login
```

### Permission denied errors
```bash
# Controlla config
akaion config --show

# Verifica permissions section
# Aggiungi path necessari a allowed_paths
```

### Connection errors
```bash
# Test connessione
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.akaion.com/health

# Verifica URL in config
akaion config --show | grep api_url
```

### Tool execution fails
```bash
# Controlla logs
akaion logs --tail 100

# Verifica tool enabled
akaion config --show | grep -A 5 "tools:"

# Test permission
# Aggiungi tool a tools.enabled in config
```

## 🔄 Updates

```bash
# Pull latest changes
cd akaion-runner
git pull

# Reinstall
./install.sh

# Restart runner
akaion run
```

## 📚 Esempi

### Task Semplice
```bash
akaion run --once --task "Lista i file in ~/Documents"
```

### Workflow Multi-Step
Il cloud può inviare workflow complessi:
```json
{
  "type": "workflow",
  "steps": [
    {"type": "command", "payload": {"command": "Leggi file config.yaml"}},
    {"type": "ai_task", "payload": {"prompt": "Analizza la configurazione"}},
    {"type": "tool", "payload": {"tool": "shell", "args": {"command": "git status"}}}
  ]
}
```

### Custom AI Provider
```bash
# Modifica config
akaion config --edit

# Cambia provider
ai:
  provider: "openai"
  model: "gpt-4"

# Restart
akaion run
```

## 💡 Best Practices

1. **Permissions**: Start con minimal permissions, aggiungi quando necessario
2. **Monitoring**: Usa `akaion logs --follow` durante development
3. **Testing**: Testa con `--once` prima di usare daemon mode
4. **Backup**: Fai backup di `~/.akaion/config.yaml`
5. **Updates**: Tieni aggiornato il runner per nuove features

## 🆘 Support

- Docs: `README.md` e `ARCHITECTURE.md`
- Issues: GitHub Issues
- Logs: `logs/runner.log`
- Status: `akaion status --verbose`
