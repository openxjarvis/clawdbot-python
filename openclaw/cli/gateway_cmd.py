"""Gateway management commands"""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..config.loader import load_config

console = Console()
gateway_app = typer.Typer(help="Gateway server management")


@gateway_app.command("run")
def run(
    port: int = typer.Option(None, "--port", "-p", help="WebSocket port"),
    bind: str = typer.Option("loopback", "--bind", help="Bind mode (loopback|lan|auto)"),
    force: bool = typer.Option(False, "--force", help="Kill existing listener on port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Run the Gateway server (foreground)"""
    try:
        import logging
        import subprocess
        import signal
        from ..gateway.bootstrap import GatewayBootstrap

        # Load .env files at startup — mirrors TS index.ts: loadDotEnv({ quiet: true })
        # Priority: CWD .env → ~/.openclaw/.env (neither overrides already-set vars)
        try:
            from ..infra.dotenv import load_dot_env
            load_dot_env(quiet=True)
        except Exception:
            pass

        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        config = load_config()
        
        if port:
            if not config.gateway:
                from ..config.schema import GatewayConfig
                config.gateway = GatewayConfig()
            config.gateway.port = port
        
        gateway_port = config.gateway.port if config.gateway else 18789
        web_port = 8080  # Control UI port
        
        # If --force, kill any processes on the target ports
        if force:
            for check_port in [gateway_port, web_port]:
                try:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{check_port}"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        pids = result.stdout.strip().split("\n")
                        for pid in pids:
                            if pid:
                                console.print(f"[yellow]Killing process {pid} on port {check_port}[/yellow]")
                                try:
                                    subprocess.run(["kill", "-9", pid], check=False)
                                except Exception:
                                    pass
                        import time
                        time.sleep(1)  # Wait for ports to be released
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not check/clear port {check_port}: {e}[/yellow]")
        
        console.print(f"[cyan]Starting Gateway on port {gateway_port}...[/cyan]")
        
        # Use bootstrap to initialize all components
        bootstrap = GatewayBootstrap()
        
        async def run_with_bootstrap():
            await bootstrap.bootstrap()
            console.print(f"[green]✓[/green] Gateway listening on ws://127.0.0.1:{gateway_port}")
            console.print("Press Ctrl+C to stop\n")
            
            # Keep running forever
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
        
        asyncio.run(run_with_bootstrap())
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Gateway stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@gateway_app.command("status")
def status(
    probe: bool = typer.Option(True, "--probe/--no-probe", help="Probe gateway via RPC"),
    deep: bool = typer.Option(False, "--deep", help="Scan system-level services"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Show gateway service status — delegates to daemon status"""
    from .daemon_cmd import daemon_status
    daemon_status(probe=probe, deep=deep, json_output=json_output,
                  url=None, token=None, timeout=10_000)


@gateway_app.command("install")
def install(
    port: int = typer.Option(18789, "--port", help="Gateway port"),
    force: bool = typer.Option(False, "--force", help="Reinstall if already installed"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Install the Gateway service (launchd/systemd)"""
    from .daemon_cmd import daemon_install
    daemon_install(port=port, force=force, json_output=json_output)


@gateway_app.command("uninstall")
def uninstall(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Uninstall the Gateway service"""
    from .daemon_cmd import daemon_uninstall
    daemon_uninstall(json_output=json_output)


@gateway_app.command("start")
def start(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Start the Gateway service"""
    from .daemon_cmd import daemon_start
    daemon_start(json_output=json_output)


@gateway_app.command("stop")
def stop(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Stop the Gateway service"""
    from .daemon_cmd import daemon_stop
    daemon_stop(json_output=json_output)


@gateway_app.command("restart")
def restart(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Restart the Gateway service"""
    from .daemon_cmd import daemon_restart
    daemon_restart(json_output=json_output)


@gateway_app.command("call")
def call(
    method: str = typer.Argument(..., help="RPC method name"),
    params: str = typer.Option("{}", "--params", help="JSON params"),
):
    """Call a Gateway RPC method"""
    console.print("[yellow]⚠[/yellow]  Gateway RPC call not yet implemented")
    console.print(f"Method: {method}")
    console.print(f"Params: {params}")


@gateway_app.command("cost")
def cost(
    days: int = typer.Option(30, "--days", help="Number of days"),
):
    """Show cost/usage summary"""
    console.print("[yellow]⚠[/yellow]  Cost tracking not yet implemented")
    console.print(f"Would show last {days} days of usage")
