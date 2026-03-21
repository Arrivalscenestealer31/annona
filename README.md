# Akaion Runner

Local agent runner che si interfaccia con il cloud Akaion per eseguire tasks, tools e skills in locale.

## 🚀 Caratteristiche

- **CLI completa**: login, init, run, status
- **Daemon persistente**: polling continuo dal cloud
- **Tool execution locale**: esegui tasks sul tuo sistema
- **Permissions**: controllo granulare su file, cartelle, operazioni
- **AI flessibile**: usa backend AI Akaion o providers esterni (OpenAI, Anthropic, Google)
- **Sincronizzazione**: offline-first con sync quando necessario
- 🎨 **UI colorata** con banner ASCII
- 🔍 **Detection automatica** OS e shell
- 🛡️ **Error handling** robusto
- 📦 **Cleanup automatico** su errore

## 📦 Installazione

### Quick Install (Una Riga)

```bash
curl -fsSL https://install.akaion.com/runner.sh | bash
```

### Manuale

```bash
git clone https://github.com/akaion/akaion-runner.git
cd akaion-runner
./install.sh
```

Vedi [INSTALL.md](INSTALL.md) per istruzioni dettagliate.

## 🔧 Setup

### 1. Login
```bash
akaion login
# Inserisci API key dal tuo account Akaion
```

### 2. Inizializza
```bash
akaion init
# Configura permissions, paths, AI provider
```

### 3. Avvia il runner
```bash
akaion run
# Avvia il daemon in background
```

### 4. Controlla lo stato
```bash
akaion status
```

## 🏗️ Architettura

```
akaion-runner/
├── cli.py                 # Entry point CLI
├── runner/
│   ├── main.py           # Daemon loop principale
│   ├── executor.py       # Esecuzione tasks
│   ├── auth.py           # Autenticazione
│   ├── config.py         # Gestione configurazione
│   ├── cloud_client.py   # Client per backend cloud
│   ├── ai_client.py      # Client AI (multi-provider)
│   ├── tools/            # Tools locali
│   │   ├── __init__.py
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   ├── browser.py
│   │   └── registry.py
│   └── permissions/      # Sistema permessi
│       ├── __init__.py
│       ├── manager.py
│       └── validator.py
├── config.yaml           # Config template
├── setup.py
└── requirements.txt
```

## 🔐 Permissions

Il runner richiede esplicito permesso per:
- Accedere a cartelle specifiche
- Eseguire comandi shell
- Modificare file
- Accedere al network
- Leggere variabili d'ambiente

## 🤖 AI Providers

Supportati:
- **Akaion AI** (backend proprietario)
- **OpenAI** (GPT-4, GPT-3.5)
- **Anthropic** (Claude)
- **Google** (Gemini)
- **Local** (Ollama, LM Studio)

## 📝 Esempi

### Task semplice
```bash
akaion run --once "Analizza i log in /var/logs"
```

### Daemon mode
```bash
akaion run --daemon
```

### Debug
```bash
akaion status --verbose
akaion logs --tail 100
```

## 🔄 Workflow

1. Runner fa polling al cloud ogni X secondi
2. Cloud invia task da eseguire
3. Runner valida permissions
4. Executor esegue il task usando tools
5. Risultato viene inviato al cloud
6. Loop continua

## 🛠️ Development

```bash
# Setup dev environment
python -m venv env
source env/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run locally
python cli.py run --dev
```

## 📄 License

Proprietary - Akaion 2026
