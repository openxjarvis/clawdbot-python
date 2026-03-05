"""Sandbox management CLI commands"""

from __future__ import annotations

import asyncio
import json as _json
import sys

import typer
from rich.console import Console
from rich.table import Table

console = Console()
sandbox_app = typer.Typer(help="Sandbox tools — manage Docker sandbox containers")


@sandbox_app.command("status")
def status(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show live status of all tracked sandbox containers."""
    try:
        from openclaw.agents.sandbox.manage import list_sandbox_containers

        containers = asyncio.run(list_sandbox_containers())

        if json_output:
            data = [
                {
                    "name": c.container_name,
                    "running": c.running,
                    "image": c.image,
                    "image_match": c.image_match,
                    "session_key": c.session_key,
                    "created_at_ms": c.created_at_ms,
                    "last_used_at_ms": c.last_used_at_ms,
                }
                for c in containers
            ]
            console.print_json(_json.dumps(data))
            return

        if not containers:
            console.print("[dim]No sandbox containers tracked.[/dim]")
            return

        table = Table(title="Sandbox Containers", show_lines=True)
        table.add_column("Container", style="cyan", no_wrap=True)
        table.add_column("Running", justify="center")
        table.add_column("Image Match", justify="center")
        table.add_column("Session Key")
        table.add_column("Image")

        for c in containers:
            running_str = "[green]✓[/green]" if c.running else "[red]✗[/red]"
            image_ok = "[green]✓[/green]" if c.image_match else "[yellow]![/yellow]"
            table.add_row(c.container_name, running_str, image_ok, c.session_key, c.image)

        console.print(table)

    except ImportError as exc:
        console.print(f"[red]Sandbox module unavailable:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


@sandbox_app.command("test")
def test() -> None:
    """Test sandbox capabilities (Docker availability and image check)."""
    try:
        import subprocess

        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            console.print("[green]✓[/green] Docker is available")
        else:
            console.print("[red]✗[/red] Docker is not available or not running")
            console.print(f"  {result.stderr.strip()}")
            raise typer.Exit(1)

        # Check default sandbox image
        from openclaw.agents.sandbox.constants import DEFAULT_SANDBOX_IMAGE
        img_result = subprocess.run(
            ["docker", "image", "inspect", DEFAULT_SANDBOX_IMAGE],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if img_result.returncode == 0:
            console.print(f"[green]✓[/green] Sandbox image present: {DEFAULT_SANDBOX_IMAGE}")
        else:
            console.print(f"[yellow]![/yellow] Sandbox image not found: {DEFAULT_SANDBOX_IMAGE}")
            console.print("  Run [bold]openclaw sandbox build[/bold] to build it first.")

        console.print("[green]Sandbox test complete.[/green]")

    except FileNotFoundError:
        console.print("[red]✗[/red] Docker executable not found. Is Docker installed?")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


@sandbox_app.command("prune")
def prune(
    idle_hours: int = typer.Option(24, "--idle-hours", help="Prune containers idle > N hours"),
    max_age_days: int = typer.Option(7, "--max-age-days", help="Prune containers older than N days"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip rate-limit check"),
) -> None:
    """Remove stale sandbox containers."""
    try:
        from openclaw.agents.sandbox import prune as _prune_mod

        if force:
            # Reset last-prune timestamp to bypass rate-limit
            _prune_mod._last_prune_at_ms = 0.0

        asyncio.run(
            _prune_mod.maybe_prune_sandboxes(
                idle_hours=idle_hours,
                max_age_days=max_age_days,
            )
        )
        console.print("[green]✓[/green] Sandbox prune complete.")

    except ImportError as exc:
        console.print(f"[red]Sandbox module unavailable:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


@sandbox_app.command("rm")
def rm(
    container_name: str = typer.Argument(..., help="Container name to remove"),
) -> None:
    """Force-remove a specific sandbox container."""
    try:
        from openclaw.agents.sandbox.manage import remove_sandbox_container

        asyncio.run(remove_sandbox_container(container_name))
        console.print(f"[green]✓[/green] Removed container: {container_name}")

    except ImportError as exc:
        console.print(f"[red]Sandbox module unavailable:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
