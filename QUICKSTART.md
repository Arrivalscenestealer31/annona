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
