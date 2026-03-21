#!/usr/bin/env python3
"""
Akaion Runner CLI

Main entry point per gestire il runner locale.
"""
import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from runner.auth import AuthManager, firebase_browser_login
from runner.config import ConfigManager
from runner.main import RunnerDaemon
from runner.cloud_client import CloudClient, MainBackendClient
from runner.banner import print_simple_logo

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
        backend_url = os.getenv("AKAION_MAIN_URL")

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
    daemon: bool = typer.Option(True, "--daemon/--once", "-d/-o", help="Run as daemon or execute once"),
    dev: bool = typer.Option(False, "--dev", help="Development mode with verbose logging"),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Execute specific task (once mode)"),
):
    """
    🚀 Avvia il runner
    """
    try:
        # Verifica autenticazione
        auth_manager = AuthManager()
        if not auth_manager.is_authenticated():
            console.print("❌ [red]Not authenticated. Run 'akaion login' first.[/red]")
            raise typer.Exit(1)
        
        # Carica config
        config_manager = ConfigManager()
        if not config_manager.config_exists():
            console.print("❌ [red]Configuration not found. Run 'akaion init' first.[/red]")
            raise typer.Exit(1)
        
        config = config_manager.load_config()
        
        # Crea e avvia runner
        runner = RunnerDaemon(config, dev_mode=dev)
        
        if daemon:
            console.print("🚀 [green]Starting Akaion Runner daemon...[/green]")
            console.print(f"Runner ID: [cyan]{auth_manager.get_runner_id()}[/cyan]")
            console.print("\nPress Ctrl+C to stop\n")
            runner.start_daemon()
        else:
            if task:
                console.print(f"🎯 [green]Executing task:[/green] {task}")
                result = runner.execute_once(task)
                console.print(f"\n✅ Result: {result}")
            else:
                console.print("🔄 [green]Polling for one task...[/green]")
                runner.poll_once()
        
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
