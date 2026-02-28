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


@gateway_app.command("probe")
def probe(
    host: str = typer.Option("127.0.0.1", "--host", help="Gateway host"),
    port: int = typer.Option(4747, "--port", "-p", help="Gateway HTTP port"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Ping the Gateway HTTP endpoint and report latency"""
    import socket
    import time

    url = f"http://{host}:{port}/health"
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=5):
            latency_ms = int((time.monotonic() - start) * 1000)
        status = "ok"
        msg = f"Gateway reachable at {host}:{port} ({latency_ms} ms)"
        if json_output:
            print(json.dumps({"status": status, "host": host, "port": port, "latency_ms": latency_ms}))
        else:
            console.print(f"[green]✓[/green] {msg}")
    except (ConnectionRefusedError, OSError) as e:
        status = "error"
        if json_output:
            print(json.dumps({"status": status, "host": host, "port": port, "error": str(e)}))
        else:
            console.print(f"[red]✗[/red] Gateway not reachable at {host}:{port}: {e}")
        raise typer.Exit(1)


@gateway_app.command("discover")
def discover(
    timeout: float = typer.Option(5.0, "--timeout", help="Discovery timeout in seconds"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Browse Bonjour/mDNS for nearby OpenClaw gateways"""
    try:
        from zeroconf import ServiceBrowser, Zeroconf

        SERVICE_TYPE = "_openclaw-gw._tcp.local."
        found: list[dict] = []

        class _Listener:
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info:
                    found.append({
                        "name": name,
                        "host": socket_addr(info),
                        "port": info.port,
                        "properties": {k.decode(): v.decode() if isinstance(v, bytes) else v
                                       for k, v in (info.properties or {}).items()},
                    })

            def remove_service(self, *_): pass
            def update_service(self, *_): pass

        def socket_addr(info):
            import socket as _s
            try:
                return _s.inet_ntoa(info.addresses[0]) if info.addresses else info.server
            except Exception:
                return info.server or "unknown"

        zc = Zeroconf()
        _Listener_inst = _Listener()
        browser = ServiceBrowser(zc, SERVICE_TYPE, _Listener_inst)
        import time
        time.sleep(timeout)
        zc.close()

        if json_output:
            print(json.dumps(found, indent=2))
        else:
            if not found:
                console.print("[yellow]No OpenClaw gateways found via mDNS[/yellow]")
            else:
                t = Table(title="Discovered Gateways")
                t.add_column("Name")
                t.add_column("Host")
                t.add_column("Port")
                for gw in found:
                    t.add_row(gw["name"], gw["host"], str(gw["port"]))
                console.print(t)
    except ImportError:
        console.print("[yellow]⚠[/yellow]  zeroconf not installed. Run: uv add zeroconf")
        raise typer.Exit(1)


@gateway_app.command("health")
def health(
    host: str = typer.Option("127.0.0.1", "--host", help="Gateway host"),
    port: int = typer.Option(4747, "--port", "-p", help="Gateway HTTP port"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Call the Gateway health RPC and print a structured summary"""
    import urllib.request
    import urllib.error

    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if json_output:
            print(json.dumps(data, indent=2))
        else:
            console.print(f"[green]✓[/green] Gateway health: [bold]{data.get('status', 'ok')}[/bold]")
            for k, v in data.items():
                if k != "status":
                    console.print(f"  {k}: {v}")
    except urllib.error.URLError as e:
        if json_output:
            print(json.dumps({"status": "error", "error": str(e)}))
        else:
            console.print(f"[red]✗[/red] Could not reach gateway at {host}:{port}: {e}")
        raise typer.Exit(1)
    except Exception as e:
        if json_output:
            print(json.dumps({"status": "error", "error": str(e)}))
        else:
            console.print(f"[red]✗[/red] Gateway health check failed: {e}")
        raise typer.Exit(1)
