"""DNS helpers CLI commands — mirrors TS src/cli/dns-cli.ts"""
from __future__ import annotations

import typer
from rich.console import Console

console = Console()
dns_app = typer.Typer(help="DNS and mDNS/Bonjour setup helpers")


@dns_app.command("setup")
def dns_setup():
    """Setup DNS-SD/Bonjour for gateway discovery"""
    console.print("[cyan]DNS-SD / Bonjour setup[/cyan]")
    console.print("  Configures mDNS advertisement for local gateway discovery.")
    console.print("[yellow]⚠[/yellow]  mDNS advertisement requires the gateway to be running.")
    console.print("Start with: [cyan]openclaw gateway run[/cyan]")


__all__ = ["dns_app"]
