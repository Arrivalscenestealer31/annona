#!/usr/bin/env python3
"""
Akaion Runner CLI

Main entry point per gestire il runner locale.
"""
import typer
from typing import Optional, List
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint
import sys
import os
import shutil
import subprocess
import tempfile
from dotenv import load_dotenv

load_dotenv()

from runner.auth import AuthManager, firebase_browser_login
from runner.config import ConfigManager
from runner.main import RunnerDaemon
from runner.cloud_client import CloudClient, MainBackendClient
from runner.banner import print_simple_logo
from runner.service_urls import resolve_service_url
from runner.brain.manager import BrainManager
from runner.brain.models import (
    Note,
    SYNC_LOCAL_ONLY,
    SYNC_PENDING,
    SYNC_SYNCED,
    SYNC_ERROR,
)
from runner.sync.engine import SyncEngine

app = typer.Typer(
    name="akaion",
    help="🚀 Akaion Runner - Local agent for cloud tasks execution",
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich"
)

console = Console()


@app.command()
def login(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Login con email+password (invece di Google)"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Password (solo con --email)"),
):
    """
    🔐 Autentica il runner con il cloud Akaion

    Default: apre il browser per il login con Google (come gcloud auth login).
    Usa --email per il login con email+password.
    """
    try:
        auth_manager = AuthManager()
        backend_url = resolve_service_url("main")

        # ─── Branch: email + password ───
        if email:
            if not password:
                password = typer.prompt("Password", hide_input=True)
            console.print("🔐 Signing in with email/password...")
            try:
                resp = AuthManager.firebase_sign_in(email, password)
            except ValueError as e:
                console.print(f"❌ [red]{e}[/red]")
                raise typer.Exit(1)
            firebase_token = resp["idToken"]
            refresh_token  = resp["refreshToken"]
            expires_in     = int(resp.get("expiresIn", 3600))

        # ─── Branch: Google OAuth (browser) ───
        else:
            console.print("🌐 Apertura browser per il login con Google...")
            console.print("   Completa il login nel browser, poi torna qui.")
            try:
                result = firebase_browser_login(timeout=120)
            except TimeoutError:
                console.print("❌ [red]Timeout: login non completato entro 2 minuti[/red]")
                raise typer.Exit(1)
            firebase_token = result["idToken"]
            refresh_token  = result["refreshToken"]
            email          = result.get("email", "")
            expires_in     = 3600

        # ─── Sync con backend Akaion ───
        console.print("🔍 Syncing with Akaion backend...")
        cloud_client = MainBackendClient(api_key=firebase_token, base_url=backend_url)
        try:
            sync_resp = cloud_client.client.post(
                "/api/v1/auth/firebase/verify",
                json={"firebase_token": firebase_token, "provider": "google.com"},
            )
            if sync_resp.status_code not in (200, 201):
                console.print(f"⚠️  [yellow]Backend sync warning ({sync_resp.status_code})[/yellow]")
        except Exception as e:
            console.print(f"⚠️  [yellow]Backend sync skipped: {e}[/yellow]")

        # ─── Salva credenziali ───
        auth_manager.save_credentials(firebase_token, refresh_token, expires_in, email=email)

        console.print("✅ [green]Successfully authenticated![/green]")
        if email:
            console.print(f"   Email:     [cyan]{email}[/cyan]")
        console.print(f"   Runner ID: [cyan]{auth_manager.get_runner_id()}[/cyan]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Error during login: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def init(
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-n", help="Interactive setup"),
):
    """
    🔧 Inizializza la configurazione del runner
    """
    try:
        config_manager = ConfigManager()
        
        if interactive:
            console.print("🔧 [bold]Akaion Runner Setup[/bold]\n")
            
            # AI Provider
            ai_provider = typer.prompt(
                "AI Provider (akaion/openai/anthropic/google/local)",
                default="akaion"
            )
            
            # Permissions
            console.print("\n📂 [bold]Filesystem Permissions[/bold]")
            allowed_paths = typer.prompt(
                "Allowed paths (comma-separated)",
                default="~/Documents,~/Downloads"
            )
            
            shell_enabled = typer.confirm("Enable shell commands?", default=True)
            
            # Crea config
            config_data = {
                "ai": {"provider": ai_provider},
                "permissions": {
                    "filesystem": {
                        "allowed_paths": [p.strip() for p in allowed_paths.split(",")]
                    },
                    "shell": {"enabled": shell_enabled}
                }
            }
            
            config_manager.create_config(config_data)
        else:
            config_manager.create_default_config()
        
        console.print("✅ [green]Configuration initialized![/green]")
        console.print(f"Config file: [cyan]{config_manager.config_path}[/cyan]")
        
    except Exception as e:
        console.print(f"❌ [red]Error during initialization: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def run(
    daemon: bool = typer.Option(True, "--daemon/--once", "-d/-o", help="Run as daemon (long-lived UI server) or execute one task"),
    dev: bool = typer.Option(False, "--dev", help="Development mode with verbose logging"),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Execute specific task (--once mode)"),
    port: int = typer.Option(7070, "--port", help="Porta del server API locale (default: 7070)"),
    brain_dir: Optional[Path] = typer.Option(None, "--brain-dir", help="Directory del brain locale (default: ~/akaion-brain)"),
    no_cloud: bool = typer.Option(False, "--no-cloud", help="Forza la modalità locale per questo run (override su cloud.enabled)"),
):
    """
    🚀 Avvia il runner
    """
    try:
        # Verifica autenticazione (non bloccante — local-first)
        auth_manager = AuthManager()
        if not auth_manager.is_authenticated():
            console.print("ℹ️  [dim]Non autenticato — avvio in modalità locale (Obsidian-like).[/dim]")
            console.print("   Apri http://127.0.0.1:7070 per usare il Brain locale.")
            console.print("   Per sincronizzare al cloud: clicca \"Sincronizza con Akaion Cloud\" in sidebar,")
            console.print("   oppure usa [cyan]akaion login[/cyan].")

        # Carica config
        config_manager = ConfigManager()
        if not config_manager.config_exists():
            console.print("❌ [red]Configuration not found. Run 'akaion init' first.[/red]")
            raise typer.Exit(1)

        config = config_manager.load_config()

        # --no-cloud override (non persistente)
        if no_cloud:
            config.setdefault("cloud", {})["enabled"] = False
            console.print("⚙️  [dim]--no-cloud: cloud sync disabled for this run[/dim]")

        # Crea e avvia runner
        runner = RunnerDaemon(config, dev_mode=dev, brain_dir=brain_dir, local_port=port)
        
        if daemon:
            console.print("🚀 [green]Starting Akaion Runner daemon...[/green]")
            console.print(f"Runner ID: [cyan]{auth_manager.get_runner_id()}[/cyan]")
            console.print("\nPress Ctrl+C to stop\n")
            runner.start_daemon()
        else:
            if not task:
                console.print("❌ [red]--once requires --task <description>[/red]")
                raise typer.Exit(2)
            console.print(f"🎯 [green]Executing task:[/green] {task}")
            result = runner.execute_once(task)
            console.print(f"\n✅ Result: {result}")
        
    except KeyboardInterrupt:
        console.print("\n👋 [yellow]Runner stopped by user[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"❌ [red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed status"),
):
    """
    📊 Mostra lo stato del runner
    """
    try:
        auth_manager = AuthManager()
        config_manager = ConfigManager()
        
        # Table
        table = Table(title="🚀 Akaion Runner Status")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="white")
        
        # Authentication
        auth_status = "✅ Authenticated" if auth_manager.is_authenticated() else "❌ Not authenticated"
        runner_id = auth_manager.get_runner_id() if auth_manager.is_authenticated() else "N/A"
        table.add_row("Authentication", auth_status, runner_id)
        
        # Configuration
        config_status = "✅ Configured" if config_manager.config_exists() else "❌ Not configured"
        config_path = str(config_manager.config_path) if config_manager.config_exists() else "N/A"
        table.add_row("Configuration", config_status, config_path)
        
        # Cloud connection
        if auth_manager.is_authenticated():
            cloud_client = MainBackendClient(api_key=auth_manager.get_api_key())
            cloud_status = "✅ Connected" if cloud_client.health_check() else "❌ Disconnected"
            table.add_row("Cloud Connection", cloud_status, cloud_client.base_url)
        
        console.print(table)
        
        if verbose and config_manager.config_exists():
            console.print("\n[bold]Configuration:[/bold]")
            config = config_manager.load_config()
            rprint(config)
        
    except Exception as e:
        console.print(f"❌ [red]Error checking status: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def logs(
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
):
    """
    📜 Mostra i log del runner
    """
    try:
        log_file = Path("logs/runner.log")
        
        if not log_file.exists():
            console.print("❌ [red]No log file found[/red]")
            raise typer.Exit(1)
        
        if follow:
            console.print(f"📜 Following {log_file}... (Ctrl+C to stop)\n")
            import subprocess
            subprocess.run(["tail", "-f", str(log_file)])
        else:
            with open(log_file) as f:
                lines = f.readlines()
                for line in lines[-tail:]:
                    console.print(line.rstrip())
        
    except KeyboardInterrupt:
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"❌ [red]Error reading logs: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    edit: bool = typer.Option(False, "--edit", "-e", help="Edit configuration file"),
    reset: bool = typer.Option(False, "--reset", "-r", help="Reset to default configuration"),
):
    """
    ⚙️  Gestisci la configurazione
    """
    try:
        config_manager = ConfigManager()
        
        if reset:
            if typer.confirm("Are you sure you want to reset configuration?"):
                config_manager.reset_config()
                console.print("✅ [green]Configuration reset to defaults[/green]")
        elif edit:
            import subprocess
            editor = os.getenv("EDITOR", "nano")
            subprocess.run([editor, str(config_manager.config_path)])
        elif show:
            if config_manager.config_exists():
                config = config_manager.load_config()
                rprint(config)
            else:
                console.print("❌ [red]Configuration not found[/red]")
        else:
            console.print(f"Config file: [cyan]{config_manager.config_path}[/cyan]")
        
    except Exception as e:
        console.print(f"❌ [red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def logout():
    """
    🚪 Logout e rimuovi credenziali
    """
    try:
        if typer.confirm("Are you sure you want to logout?"):
            auth_manager = AuthManager()
            auth_manager.clear_credentials()
            console.print("✅ [green]Successfully logged out[/green]")
    except Exception as e:
        console.print(f"❌ [red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """
    📌 Mostra la versione
    """
    print_simple_logo()
    console.print()
    console.print("Version: [green]0.1.0[/green]")
    console.print("Python: [yellow]" + sys.version.split()[0] + "[/yellow]")
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# Brain note & sync sub-apps
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_BRAIN_DIR = Path.home() / "akaion-brain"

note_app = typer.Typer(
    name="note",
    help="📝 Gestisci le note del brain locale",
    no_args_is_help=True,
)

sync_app = typer.Typer(
    name="sync",
    help="🔄 Sincronizza il brain locale con il cloud COT",
    no_args_is_help=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_VALID_SYNC_STATUSES = {SYNC_LOCAL_ONLY, SYNC_PENDING, SYNC_SYNCED, SYNC_ERROR}

_STATUS_STYLE = {
    SYNC_LOCAL_ONLY: "dim",
    SYNC_PENDING:    "yellow",
    SYNC_SYNCED:     "green",
    SYNC_ERROR:      "red",
}


def _resolve_brain_dir() -> Path:
    """Risolve la brain dir dal config (se esiste) o usa il default."""
    config_manager = ConfigManager()
    if config_manager.config_exists():
        try:
            cfg = config_manager.load_config() or {}
            d = cfg.get("brain", {}).get("dir")
            if d:
                return Path(d).expanduser()
        except Exception:
            pass
    # Permette override via env (utile per i test)
    env_dir = os.getenv("AKAION_BRAIN_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return DEFAULT_BRAIN_DIR


def _open_brain() -> BrainManager:
    return BrainManager(_resolve_brain_dir())


def _find_editor() -> str:
    """$EDITOR → nano → vi → vim (primo trovato in PATH)."""
    editor = os.getenv("EDITOR")
    if editor and shutil.which(editor.split()[0]):
        return editor
    for candidate in ("nano", "vi", "vim"):
        if shutil.which(candidate):
            return candidate
    raise RuntimeError(
        "Nessun editor trovato. Imposta $EDITOR o installa nano/vi/vim."
    )


def _edit_in_editor(initial_content: str = "", suffix: str = ".md") -> str:
    """Apre $EDITOR su un tmpfile precaricato e ritorna il contenuto finale."""
    editor = _find_editor()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(initial_content)
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(f"{editor} {tmp_path}", shell=True, check=True)
        return tmp_path.read_text(encoding="utf-8")
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _resolve_id(brain: BrainManager, prefix: str) -> str:
    """Risolve un id prefix → id completo (errore se ambiguo o nessun match)."""
    # Match esatto: corto-circuita
    if brain.get(prefix):
        return prefix
    rows = brain._conn.execute(
        "SELECT id, title FROM notes WHERE id LIKE ? LIMIT 10",
        (prefix + "%",),
    ).fetchall()
    if not rows:
        console.print(f"❌ [red]Nessuna nota con id che inizia per '{prefix}'[/red]")
        raise typer.Exit(1)
    if len(rows) > 1:
        console.print(f"❌ [red]Id ambiguo '{prefix}' — {len(rows)} match:[/red]")
        for r in rows:
            console.print(f"   [dim]{r['id'][:12]}[/dim]  {r['title']}")
        raise typer.Exit(1)
    return rows[0]["id"]


def _short(note_id: str) -> str:
    return note_id[:8]


def _fmt_dt(dt) -> str:
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M")


def _notes_table(title: str, notes: List[Note]) -> Table:
    table = Table(title=title)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Tags", style="magenta")
    table.add_column("Sync", style="white")
    table.add_column("Updated", style="dim")
    for n in notes:
        style = _STATUS_STYLE.get(n.sync_status, "white")
        table.add_row(
            _short(n.id),
            n.title or "(untitled)",
            ", ".join(n.tags) if n.tags else "-",
            f"[{style}]{n.sync_status}[/{style}]",
            _fmt_dt(n.updated_at),
        )
    return table


def _require_auth() -> AuthManager:
    auth = AuthManager()
    if not auth.is_authenticated():
        console.print(
            "❌ [red]Non sei loggato.[/red] Esegui [cyan]akaion login[/cyan] "
            "per pushare al cloud, oppure usa l'UI ([cyan]http://127.0.0.1:7070[/cyan]) "
            "cliccando \"Sincronizza con Akaion Cloud\"."
        )
        raise typer.Exit(1)
    return auth


def _build_sync_engine(brain: BrainManager) -> SyncEngine:
    auth = _require_auth()
    return SyncEngine(brain=brain, cot_url=resolve_service_url("cot"), auth=auth)


# ──────────────────────────────────────────────────────────────────────────────
# `akaion note ...`
# ──────────────────────────────────────────────────────────────────────────────


@note_app.command("add")
def note_add(
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Titolo della nota"),
    tag: List[str] = typer.Option([], "--tag", help="Tag (ripetibile)"),
    from_file: Optional[Path] = typer.Option(None, "--from-file", "-f", help="Leggi il contenuto da file"),
    stdin: bool = typer.Option(False, "--stdin", help="Leggi il contenuto da stdin"),
):
    """
    📝 Crea una nuova nota local_only.

    Senza --stdin / --from-file apre l'editor ($EDITOR, fallback nano/vi/vim).
    """
    try:
        # Contenuto
        if stdin and from_file:
            console.print("❌ [red]--stdin e --from-file sono mutuamente esclusivi[/red]")
            raise typer.Exit(1)

        if stdin:
            content = sys.stdin.read()
        elif from_file:
            if not from_file.exists():
                console.print(f"❌ [red]File non trovato: {from_file}[/red]")
                raise typer.Exit(1)
            content = from_file.read_text(encoding="utf-8")
        else:
            content = _edit_in_editor("")
            if not content.strip():
                console.print("⚠️  [yellow]Contenuto vuoto, nota non creata.[/yellow]")
                raise typer.Exit(1)

        # Titolo: --title > prima riga non vuota > "Untitled"
        if not title:
            for line in content.splitlines():
                line = line.strip().lstrip("#").strip()
                if line:
                    title = line[:120]
                    break
        if not title:
            title = "Untitled"

        brain = _open_brain()
        note = brain.create(title=title, content=content, tags=list(tag))
        path = brain._note_path(note.id)
        console.print("✅ [green]Nota creata[/green]")
        console.print(f"   ID:     [cyan]{note.id}[/cyan]")
        console.print(f"   Title:  {note.title}")
        if note.tags:
            console.print(f"   Tags:   [magenta]{', '.join(note.tags)}[/magenta]")
        console.print(f"   Path:   [dim]{path}[/dim]")
        console.print(f"   Status: [dim]{note.sync_status}[/dim]")
        brain.close()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@note_app.command("list")
def note_list(
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra per tag"),
    status: Optional[str] = typer.Option(None, "--status", help=f"Filtra per stato ({'/'.join(sorted(_VALID_SYNC_STATUSES))})"),
    limit: int = typer.Option(50, "--limit", "-n", help="Numero massimo di note"),
):
    """📋 Lista le note locali."""
    try:
        if status and status not in _VALID_SYNC_STATUSES:
            console.print(
                f"❌ [red]Stato non valido '{status}'. Valori: {', '.join(sorted(_VALID_SYNC_STATUSES))}[/red]"
            )
            raise typer.Exit(1)

        brain = _open_brain()
        notes = brain.list(sync_status=status, tag=tag, limit=limit)

        if not notes:
            console.print("ℹ️  [dim]Nessuna nota trovata.[/dim]")
            brain.close()
            return

        table = _notes_table(f"📝 Brain notes ({len(notes)})", notes)
        console.print(table)
        brain.close()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@note_app.command("show")
def note_show(
    note_id: str = typer.Argument(..., help="ID della nota (anche prefix)"),
):
    """🔍 Mostra metadata + contenuto di una nota."""
    try:
        brain = _open_brain()
        full_id = _resolve_id(brain, note_id)
        note = brain.get(full_id)
        if not note:
            console.print("❌ [red]Nota non trovata[/red]")
            raise typer.Exit(1)

        style = _STATUS_STYLE.get(note.sync_status, "white")
        console.print(f"[bold cyan]{note.title}[/bold cyan]")
        console.print(f"   ID:         [cyan]{note.id}[/cyan]")
        console.print(f"   Tags:       [magenta]{', '.join(note.tags) if note.tags else '-'}[/magenta]")
        console.print(f"   Status:     [{style}]{note.sync_status}[/{style}]")
        console.print(f"   Created:    [dim]{_fmt_dt(note.created_at)}[/dim]")
        console.print(f"   Updated:    [dim]{_fmt_dt(note.updated_at)}[/dim]")
        if note.synced_at:
            console.print(f"   Synced:     [dim]{_fmt_dt(note.synced_at)}[/dim]")
        if note.cot_message_id:
            console.print(f"   COT msg:    [dim]{note.cot_message_id}[/dim]")
        if note.cot_cluster_name:
            console.print(f"   Cluster:    [dim]{note.cot_cluster_name}[/dim]")
        if note.sync_error:
            console.print(f"   Error:      [red]{note.sync_error}[/red]")
        console.print(f"   Path:       [dim]{brain._note_path(note.id)}[/dim]")
        console.print()
        console.print("[bold]── Content ─────────────────────────────────────[/bold]")
        console.print(note.content or "[dim](empty)[/dim]")
        brain.close()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@note_app.command("edit")
def note_edit(
    note_id: str = typer.Argument(..., help="ID della nota (anche prefix)"),
):
    """✏️  Apri la nota nell'editor; se era 'synced' torna 'pending_sync'."""
    try:
        brain = _open_brain()
        full_id = _resolve_id(brain, note_id)
        note = brain.get(full_id)
        if not note:
            console.print("❌ [red]Nota non trovata[/red]")
            raise typer.Exit(1)

        new_content = _edit_in_editor(note.content or "")
        if new_content == note.content:
            console.print("ℹ️  [dim]Nessuna modifica.[/dim]")
            brain.close()
            return

        # BrainManager.update gestisce già il flip synced→pending_sync
        updated = brain.update(full_id, content=new_content)
        if updated is None:
            console.print("❌ [red]Update fallito[/red]")
            raise typer.Exit(1)

        console.print("✅ [green]Nota aggiornata[/green]")
        console.print(f"   ID:     [cyan]{updated.id}[/cyan]")
        console.print(f"   Status: [dim]{updated.sync_status}[/dim]")
        brain.close()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@note_app.command("delete")
def note_delete(
    note_id: str = typer.Argument(..., help="ID della nota (anche prefix)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Salta la conferma"),
):
    """🗑️  Elimina una nota (file markdown + indice SQLite)."""
    try:
        brain = _open_brain()
        full_id = _resolve_id(brain, note_id)
        note = brain.get(full_id)
        if not note:
            console.print("❌ [red]Nota non trovata[/red]")
            raise typer.Exit(1)

        if not yes:
            if not typer.confirm(f"Eliminare '{note.title}' ({_short(full_id)})?"):
                console.print("[dim]Annullato.[/dim]")
                brain.close()
                return

        if brain.delete(full_id):
            console.print(f"✅ [green]Nota eliminata[/green] [dim]({_short(full_id)})[/dim]")
        else:
            console.print("❌ [red]Eliminazione fallita[/red]")
            raise typer.Exit(1)
        brain.close()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@note_app.command("search")
def note_search(
    query: str = typer.Argument(..., help="Query FTS5"),
    limit: int = typer.Option(20, "--limit", "-n", help="Numero massimo di risultati"),
):
    """🔎 Ricerca full-text sul brain locale."""
    try:
        brain = _open_brain()
        notes = brain.search(query, limit=limit)
        if not notes:
            console.print(f"ℹ️  [dim]Nessun risultato per '{query}'.[/dim]")
            brain.close()
            return
        table = _notes_table(f"🔎 Risultati per '{query}' ({len(notes)})", notes)
        console.print(table)
        brain.close()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# `akaion sync ...`
# ──────────────────────────────────────────────────────────────────────────────


@sync_app.command("status")
def sync_status_cmd():
    """📊 Riepilogo dello stato di sync del brain locale."""
    try:
        brain = _open_brain()
        stats = brain.stats()

        table = Table(title="🔄 Sync status")
        table.add_column("Stato", style="cyan")
        table.add_column("Note", style="white", justify="right")
        table.add_row(f"[{_STATUS_STYLE[SYNC_LOCAL_ONLY]}]{SYNC_LOCAL_ONLY}[/]", str(stats.local_only))
        table.add_row(f"[{_STATUS_STYLE[SYNC_PENDING]}]{SYNC_PENDING}[/]", str(stats.pending))
        table.add_row(f"[{_STATUS_STYLE[SYNC_SYNCED]}]{SYNC_SYNCED}[/]", str(stats.synced))
        table.add_row(f"[{_STATUS_STYLE[SYNC_ERROR]}]{SYNC_ERROR}[/]", str(stats.errors))
        console.print(table)

        total = stats.local_only + stats.pending + stats.synced + stats.errors
        console.print(f"[dim]{total} notes total[/dim]")
        if stats.last_push:
            console.print(f"Ultimo push:  [dim]{_fmt_dt(stats.last_push)}[/dim]")
        else:
            console.print("Ultimo push:  [dim]mai[/dim]")
        if stats.last_pull:
            console.print(f"Ultimo pull:  [dim]{_fmt_dt(stats.last_pull)}[/dim]")
        brain.close()
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@sync_app.command("push")
def sync_push_cmd(
    id: List[str] = typer.Option([], "--id", help="ID (anche prefix) di una nota specifica; ripetibile"),
    all_pending: bool = typer.Option(False, "--all-pending", help="Pusha tutte le note pending"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Mostra cosa farebbe senza eseguire"),
):
    """⬆️  Push delle note verso COT."""
    try:
        if not id and not all_pending:
            console.print("❌ [red]Specifica --id <ID> [...] oppure --all-pending[/red]")
            raise typer.Exit(1)

        brain = _open_brain()

        # Risolvi target
        targets: List[Note] = []
        if id:
            for prefix in id:
                full = _resolve_id(brain, prefix)
                note = brain.get(full)
                if note:
                    targets.append(note)
        if all_pending:
            pending_notes = brain.list(sync_status=SYNC_PENDING, limit=10_000)
            seen = {n.id for n in targets}
            for n in pending_notes:
                if n.id not in seen:
                    targets.append(n)

        if not targets:
            console.print("ℹ️  [dim]Nessuna nota da pushare.[/dim]")
            brain.close()
            return

        if dry_run:
            table = _notes_table(
                f"[yellow]DRY RUN[/yellow] — {len(targets)} note da pushare", targets
            )
            console.print(table)
            console.print("[dim]Nessuna azione eseguita (--dry-run).[/dim]")
            brain.close()
            return

        # Auth prima di tutto
        engine = _build_sync_engine(brain)

        # Marca pending al volo le local_only che l'utente ha richiesto esplicitamente
        for n in targets:
            if n.sync_status == SYNC_LOCAL_ONLY:
                brain.mark_pending(n.id)

        # Push uno per uno (così facciamo report per nota)
        result_table = Table(title=f"⬆️  Push report ({len(targets)})")
        result_table.add_column("ID", style="cyan", no_wrap=True)
        result_table.add_column("Title", style="white")
        result_table.add_column("Esito", style="white")
        ok = err = 0
        for n in targets:
            success = engine.push_note(n.id)
            if success:
                ok += 1
                result_table.add_row(_short(n.id), n.title, "[green]ok[/green]")
            else:
                err += 1
                latest = brain.get(n.id)
                msg = (latest.sync_error if latest and latest.sync_error else "errore")[:60]
                result_table.add_row(_short(n.id), n.title, f"[red]err[/red] [dim]{msg}[/dim]")

        console.print(result_table)
        console.print(f"[green]{ok} ok[/green] / [red]{err} err[/red]")
        brain.close()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@sync_app.command("pull")
def sync_pull_cmd(
    since: Optional[str] = typer.Option(None, "--since", help="(ignorato per ora) filtro per data"),
):
    """⬇️  Pull dei cluster da COT (aggiorna i metadati delle note già synced)."""
    try:
        if since:
            console.print(
                f"⚠️  [yellow]--since='{since}' ignorato: il pull al momento sincronizza solo i cluster.[/yellow]"
            )
        brain = _open_brain()
        engine = _build_sync_engine(brain)
        result = engine.pull_clusters()
        console.print("✅ [green]Pull completato[/green]")
        console.print(
            f"   Clusters: [cyan]{result.get('clusters', 0)}[/cyan]"
            f"   Updated:  [cyan]{result.get('updated', 0)}[/cyan]"
        )
        brain.close()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# `akaion cloud ...`  — toggle local vs cloud-sync mode
# ──────────────────────────────────────────────────────────────────────────────

cloud_app = typer.Typer(
    name="cloud",
    help="☁️  Abilita/disabilita la sincronizzazione cloud (local-first by default)",
    no_args_is_help=True,
)


@cloud_app.command("enable")
def cloud_enable():
    """Abilita la sync con Akaion Cloud (cloud.enabled=true in config)."""
    try:
        cm = ConfigManager()
        if not cm.config_exists():
            cm.create_default_config()
        cm.set("cloud.enabled", True)
        console.print("✅ [green]Cloud sync abilitata.[/green]")
        auth = AuthManager()
        if not auth.is_authenticated():
            console.print(
                "ℹ️  [dim]Non sei loggato — esegui [cyan]akaion login[/cyan] "
                "per completare la sincronizzazione.[/dim]"
            )
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@cloud_app.command("disable")
def cloud_disable():
    """Disabilita la sync con Akaion Cloud (modalità locale pura)."""
    try:
        cm = ConfigManager()
        if not cm.config_exists():
            cm.create_default_config()
        cm.set("cloud.enabled", False)
        console.print("✅ [green]Cloud sync disabilitata — modalità locale pura.[/green]")
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


@cloud_app.command("status")
def cloud_status():
    """Mostra la modalità corrente (local vs cloud)."""
    try:
        cm = ConfigManager()
        cloud_enabled = False
        if cm.config_exists():
            cloud_enabled = bool(cm.get("cloud.enabled", False))
        auth = AuthManager()
        authed = auth.is_authenticated()
        mode = "cloud" if (cloud_enabled and authed) else "local"

        table = Table(title="☁️  Cloud mode")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("mode", f"[{'green' if mode=='cloud' else 'yellow'}]{mode}[/]")
        table.add_row("cloud.enabled", str(cloud_enabled))
        table.add_row("authenticated", str(authed))
        if authed:
            table.add_row("email", auth.get_email() or "-")
        console.print(table)
    except Exception as e:
        console.print(f"❌ [red]Errore: {e}[/red]")
        raise typer.Exit(1)


# Registriamo i sub-app sul root
app.add_typer(note_app, name="note")
app.add_typer(sync_app, name="sync")
app.add_typer(cloud_app, name="cloud")


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Show banner when running without command"""
    if ctx.invoked_subcommand is None:
        print_simple_logo()
        console.print()
        console.print("Run [cyan]akaion --help[/cyan] for available commands")
        console.print()


if __name__ == "__main__":
    app()
