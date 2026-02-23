"""Update commands — mirrors TS src/cli/update-cli.ts"""
from __future__ import annotations

import subprocess
import sys
from typing import Optional

import typer
from rich.console import Console

console = Console()
update_app = typer.Typer(help="OpenClaw update management")

_DEFAULT_TIMEOUT_SECS = 1200
_DEFAULT_STATUS_TIMEOUT_SECS = 3


@update_app.callback(invoke_without_command=True)
def update_default(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    no_restart: bool = typer.Option(False, "--no-restart", help="Skip restarting gateway"),
    channel: Optional[str] = typer.Option(None, "--channel", help="Update channel (stable|beta|dev)"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Specific npm dist-tag or version"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_SECS, "--timeout", help="Timeout in seconds"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompts"),
):
    """Update OpenClaw to the latest version"""
    if ctx.invoked_subcommand is not None:
        return
    _do_update(json_output=json_output, no_restart=no_restart, channel=channel,
               tag=tag, timeout=timeout, yes=yes)


@update_app.command("wizard")
def update_wizard():
    """Interactive update wizard"""
    console.print("[cyan]OpenClaw Update Wizard[/cyan]")
    console.print("\nCurrent installation: pip package")
    console.print("\nTo update, run:")
    console.print("  [cyan]pip install --upgrade openclaw[/cyan]")
    console.print("  or")
    console.print("  [cyan]uv pip install --upgrade openclaw[/cyan]")


@update_app.command("status")
def update_status(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    timeout: int = typer.Option(_DEFAULT_STATUS_TIMEOUT_SECS, "--timeout", help="Timeout in seconds"),
):
    """Show current version and update channel"""
    import json
    try:
        from openclaw import __version__ as current_version
    except ImportError:
        current_version = "unknown"

    status = {"version": current_version, "channel": "stable"}

    if json_output:
        console.print(json.dumps(status, indent=2))
    else:
        console.print(f"Version: [cyan]{current_version}[/cyan]")
        console.print(f"Channel: stable")
        console.print("\nCheck for updates: [cyan]pip install --upgrade openclaw[/cyan]")


def _do_update(json_output: bool, no_restart: bool, channel: Optional[str],
               tag: Optional[str], timeout: int, yes: bool):
    """Run the update."""
    import json

    pkg = f"openclaw=={tag}" if tag else "openclaw"

    if not yes:
        confirm = typer.confirm(f"Update OpenClaw ({pkg})?", default=True)
        if not confirm:
            console.print("Cancelled")
            return

    console.print(f"[cyan]Updating OpenClaw...[/cyan]")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", pkg],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            console.print("[green]✓[/green] Update complete")
            if not no_restart:
                console.print("[dim]Restart gateway to apply: openclaw daemon restart[/dim]")
        else:
            console.print(f"[red]Update failed:[/red]\n{result.stderr}")
            raise typer.Exit(1)
    except subprocess.TimeoutExpired:
        console.print(f"[red]Update timed out after {timeout}s[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


__all__ = ["update_app"]
