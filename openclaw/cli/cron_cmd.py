"""Cron management commands — mirrors TS src/cli/cron-cli.ts"""
from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()
cron_app = typer.Typer(help="Scheduled tasks (cron)", no_args_is_help=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_raw_config() -> dict:
    from pathlib import Path
    from ..config.loader import load_config_raw
    from ..config.paths import resolve_config_path
    try:
        cfg_path = resolve_config_path()
        if cfg_path and Path(cfg_path).exists():
            return load_config_raw(Path(cfg_path)) or {}
    except Exception:
        pass
    default = Path.home() / ".openclaw" / "openclaw.json"
    if default.exists():
        try:
            return load_config_raw(default) or {}
        except Exception:
            pass
    return {}


def _save_raw(raw: dict):
    from ..config.loader import write_config_file
    write_config_file(raw)


def _get_cron_jobs(raw: dict) -> dict:
    """Return cron jobs dict from config."""
    cron_section = raw.get("cron") or {}
    if isinstance(cron_section, dict):
        return cron_section.get("jobs") or {}
    return {}


# ---------------------------------------------------------------------------
# Default callback
# ---------------------------------------------------------------------------

@cron_app.callback(invoke_without_command=True)
def cron_default(ctx: typer.Context):
    """List cron jobs (default action)."""
    if ctx.invoked_subcommand is None:
        list_crons(json_output=False)


# ---------------------------------------------------------------------------
# cron list
# ---------------------------------------------------------------------------

@cron_app.command("list")
def list_crons(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
):
    """List configured cron jobs"""
    # First try gateway RPC (if running)
    try:
        from .gateway_rpc_cli import GatewayRpcOpts, call_gateway_from_cli
        opts = GatewayRpcOpts(url=url, token=token, timeout=5_000, json_output=json_output)
        result = call_gateway_from_cli("cron.list", opts, {}, show_progress=False)
        jobs = result.get("jobs", result) if isinstance(result, dict) else result or []

        if json_output:
            console.print(json.dumps(jobs, indent=2, ensure_ascii=False))
            return

        _print_jobs_table(jobs if isinstance(jobs, list) else list(jobs.values()) if isinstance(jobs, dict) else [])
        return
    except Exception:
        pass

    # Fallback: read from config
    raw = _load_raw_config()
    jobs_dict = _get_cron_jobs(raw)

    if json_output:
        console.print(json.dumps(jobs_dict, indent=2, ensure_ascii=False))
        return

    if not jobs_dict:
        console.print("[yellow]No cron jobs configured[/yellow]")
        return

    jobs_list = [
        {**v, "name": k} if isinstance(v, dict) else {"name": k, "schedule": str(v)}
        for k, v in jobs_dict.items()
    ]
    _print_jobs_table(jobs_list)


def _print_jobs_table(jobs: list):
    if not jobs:
        console.print("[yellow]No cron jobs found[/yellow]")
        return

    table = Table(title=f"Cron Jobs ({len(jobs)})")
    table.add_column("Name", style="cyan")
    table.add_column("Schedule", style="green")
    table.add_column("Enabled", style="yellow")
    table.add_column("Description", style="dim")

    for job in jobs:
        if isinstance(job, dict):
            disabled = job.get("disabled", False)
            enabled_icon = "[red]✗ disabled[/red]" if disabled else "[green]✓[/green]"
            table.add_row(
                job.get("name", ""),
                job.get("schedule") or job.get("cron", ""),
                enabled_icon,
                job.get("description") or job.get("message", ""),
            )
        else:
            table.add_row(str(job), "", "[green]✓[/green]", "")

    console.print(table)


# ---------------------------------------------------------------------------
# cron enable / disable
# ---------------------------------------------------------------------------

@cron_app.command("enable")
def enable(
    name: str = typer.Argument(..., help="Cron job name"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Enable a cron job (clears its disabled flag)"""
    raw = _load_raw_config()
    jobs = _get_cron_jobs(raw)

    if name not in jobs:
        console.print(f"[red]Cron job not found:[/red] {name}")
        console.print(f"\nAvailable jobs: {', '.join(jobs.keys()) or '(none)'}")
        raise typer.Exit(1)

    job = jobs[name]
    if isinstance(job, dict):
        job.pop("disabled", None)
    else:
        job = {"schedule": str(job)}

    raw.setdefault("cron", {}).setdefault("jobs", {})[name] = job

    try:
        _save_raw(raw)
        if json_output:
            console.print(json.dumps({"enabled": name}))
        else:
            console.print(f"[green]✓[/green] Cron job enabled: [cyan]{name}[/cyan]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@cron_app.command("disable")
def disable(
    name: str = typer.Argument(..., help="Cron job name"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Disable a cron job (sets disabled: true)"""
    raw = _load_raw_config()
    jobs = _get_cron_jobs(raw)

    if name not in jobs:
        console.print(f"[red]Cron job not found:[/red] {name}")
        console.print(f"\nAvailable jobs: {', '.join(jobs.keys()) or '(none)'}")
        raise typer.Exit(1)

    job = jobs[name]
    if isinstance(job, dict):
        job["disabled"] = True
    else:
        job = {"schedule": str(job), "disabled": True}

    raw.setdefault("cron", {}).setdefault("jobs", {})[name] = job

    try:
        _save_raw(raw)
        if json_output:
            console.print(json.dumps({"disabled": name}))
        else:
            console.print(f"[green]✓[/green] Cron job disabled: [cyan]{name}[/cyan]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
