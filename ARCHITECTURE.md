# Akaion Runner - Architecture

## 🏗️ Componenti Principali

### 1. CLI (`cli.py`)
Entry point dell'applicazione. Comandi disponibili:
- `akaion login` - Autenticazione
- `akaion init` - Setup configurazione
- `akaion run` - Avvio daemon
- `akaion status` - Stato del runner
- `akaion logs` - Visualizza log
- `akaion config` - Gestione config

### 2. Runner Daemon (`runner/main.py`)
Daemon principale che:
- Fa polling continuo dal cloud
- Gestisce heartbeat
- Esegue tasks ricevuti
- Gestisce retry e error handling

### 3. Cloud Clients (`runner/cloud_client.py`)
Client per comunicare con i 4 backend Akaion:

#### MainBackendClient
- API: `https://api.akaion.com`
- Gestisce: utenti, autenticazione, notifiche
- Endpoints principali:
  - `GET /v1/users/{id}` - Info utente
  - `POST /v1/notifications` - Crea notifica
  - `GET /v1/runner/tasks/poll` - Poll tasks

#### AIBackendClient  
- API: `https://ai.akaion.com`
- Gestisce: LLM, skills, reasoning
- Endpoints principali:
  - `POST /v1/kai/chat` - Chat completion
  - `POST /v1/skills/{name}/execute` - Esegui skill
  - `GET /v1/skills` - Lista skills

#### CalendarBackendClient
- API: `https://calendar.akaion.com`
- Gestisce: eventi, calendario
- Endpoints principali:
  - `GET /v1/events` - Lista eventi
  - `POST /v1/events` - Crea evento
  - `PUT /v1/events/{id}` - Aggiorna evento

#### CoTBackendClient
- API: `https://cot.akaion.com`
- Gestisce: workflows, chain-of-thought
- Endpoints principali:
  - `POST /v1/workflows/{id}/execute` - Esegui workflow
  - `GET /v1/workflows/executions/{id}` - Stato esecuzione
  - `POST /v1/cot/create` - Crea CoT reasoning

### 4. Autenticazione (`runner/auth.py`)
- **Metodo**: Bearer Token (JWT)
- **Storage**: Encrypted in `~/.akaion/auth.json`
- **Header**: `Authorization: Bearer <token>`
- **Extra Headers**: `X-Runner-ID` per identificazione

Gestisce:
- Encryption/decryption API key
- Runner ID univoco
- Token refresh

### 5. Executor (`runner/executor.py`)
Esegue i tasks ricevuti:
- `command` - Comandi semplici
- `tool` - Esecuzione tool specifico
- `ai_task` - Task con reasoning AI
- `workflow` - Workflow multi-step

### 6. Permission Manager (`runner/permissions/`)
Sistema granulare di permessi:

**Filesystem**:
- `allowed_paths` - Cartelle consentite
- `denied_paths` - Cartelle negate
- `max_file_size_mb` - Limite dimensioni file

**Shell**:
- `allowed_commands` - Comandi consentiti
- `denied_commands` - Comandi negati
- `timeout` - Timeout esecuzione

**Network**:
- `allowed_domains` - Domini consentiti (supporta wildcard `*.example.com`)

**System**:
- `allow_env_vars` - Accesso variabili ambiente
- `allow_process_management` - Gestione processi

### 7. Tools (`runner/tools/`)
Tools locali disponibili:

#### FilesystemTool
Operations: `read`, `write`, `list`, `exists`, `delete`
```python
{
  "tool": "filesystem",
  "args": {
    "operation": "read",
    "path": "/path/to/file"
  }
}
```

#### ShellTool
Esegue comandi shell con timeout
```python
{
  "tool": "shell",
  "args": {
    "command": "ls -la",
    "timeout": 30
  }
}
```

#### BrowserTool
HTTP requests (GET, POST)
```python
{
  "tool": "browser",
  "args": {
    "url": "https://api.example.com",
    "method": "GET"
  }
}
```

### 8. AI Client (`runner/ai_client.py`)
Client multi-provider per AI:

**Provider supportati**:
- `akaion` - Backend AI Akaion (default)
- `openai` - OpenAI GPT-4
- `anthropic` - Claude
- `google` - Gemini
- `local` - Ollama

**Funzioni**:
- `chat_completion()` - Chat con LLM
- `execute_command()` - Interpreta ed esegue comandi
- `reason_and_execute()` - Reasoning + tool execution

## 🔄 Flusso di Esecuzione

```
1. CLI start
   ↓
2. Load config & auth
   ↓
3. Initialize CloudClient (con Bearer token)
   ↓
4. Start daemon loop
   ↓
5. Poll tasks ogni N secondi
   │
   ├─→ Task ricevuto
   │   ↓
   │   Validate permissions
   │   ↓
   │   Execute via Executor
   │   ↓
   │   ├─→ Use Tools (filesystem, shell, browser)
   │   ├─→ Call AI (reasoning, skills)
   │   └─→ Call Cloud APIs (calendar, cot)
   │   ↓
   │   Submit result al cloud
   │
   └─→ Send heartbeat ogni 30s
```

## 🔐 Sicurezza

1. **API Key encryption**: Stored encrypted con Fernet
2. **Bearer Token**: Tutte le chiamate API usano JWT
3. **Permission System**: Controllo granulare pre-esecuzione
4. **File permissions**: Config files in `~/.akaion` con chmod 600
5. **Timeout**: Tutti i comandi hanno timeout

## 📊 Monitoring

**Logs**: `logs/runner.log`
- Rotation: 1 day
- Retention: 7 days
- Levels: DEBUG, INFO, WARNING, ERROR

**State**: `~/.akaion/state.json`
- Runner status
- Last heartbeat
- Tasks executed

**Health check**: `akaion status`

## 🧩 Estensibilità

### Aggiungere un nuovo Tool
```python
# runner/tools/my_tool.py
from .registry import Tool

class MyTool(Tool):
    def __init__(self, config):
        super().__init__(
            name="my_tool",
            description="What it does",
            parameters={...}
        )
    
    def execute(self, **kwargs):
        # Implementation
        return result
```

### Aggiungere un nuovo Provider AI
```python
# In runner/ai_client.py
def _init_my_provider(self):
    # Setup client
    pass

def _chat_my_provider(self, messages, temp, max_tok):
    # Execute chat
    return response
```

## 🌐 Environment Variables

```bash
# Cloud
AKAION_API_KEY=xxx
AKAION_MAIN_URL=https://api.akaion.com
AKAION_AI_URL=https://ai.akaion.com
AKAION_CALENDAR_URL=https://calendar.akaion.com
AKAION_COT_URL=https://cot.akaion.com
AKAION_RUNNER_ID=auto

# AI Providers
OPENAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
GOOGLE_API_KEY=xxx

# Dev
AKAION_DEV_MODE=false
AKAION_LOG_LEVEL=INFO
```

## 📦 Deployment

### Local Development
```bash
./install.sh
source env/bin/activate
akaion login
akaion init
akaion run --dev
```

### Production (systemd)
```bash
# /etc/systemd/system/akaion-runner.service
[Unit]
Description=Akaion Runner
After=network.target

[Service]
Type=simple
User=akaion
WorkingDirectory=/opt/akaion-runner
ExecStart=/opt/akaion-runner/env/bin/python cli.py run --daemon
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["python", "cli.py", "run", "--daemon"]
```
