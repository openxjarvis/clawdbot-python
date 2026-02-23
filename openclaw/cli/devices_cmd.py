"""Devices management CLI commands — mirrors TS src/cli/devices-cli.ts"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

console = Console()
devices_app = typer.Typer(help="Device pairing and management")


@devices_app.command("list")
def list_devices(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
):
    """List paired devices"""
    try:
        from .gateway_rpc_cli import GatewayRpcOpts, call_gateway_from_cli
        import json
        opts = GatewayRpcOpts(url=url, token=token, timeout=10_000, json_output=json_output)
        result = call_gateway_from_cli("device.list", opts, {})
        devices = result.get("devices", result) if isinstance(result, dict) else result or []
        if json_output:
            console.print(json.dumps(devices, indent=2))
        else:
            if not devices:
                console.print("[yellow]No paired devices[/yellow]")
            else:
                for d in (devices if isinstance(devices, list) else []):
                    if isinstance(d, dict):
                        console.print(f"  {d.get('id', '')} — {d.get('name', '')}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@devices_app.command("pair")
def pair_device(
    device_id: str = typer.Argument(..., help="Device ID or pairing code"),
    name: Optional[str] = typer.Option(None, "--name", help="Friendly name"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
):
    """Pair a new device"""
    try:
        from .gateway_rpc_cli import GatewayRpcOpts, call_gateway_from_cli
        opts = GatewayRpcOpts(url=url, token=token, timeout=15_000)
        params = {"deviceId": device_id}
        if name:
            params["name"] = name
        result = call_gateway_from_cli("device.pair", opts, params)
        console.print(f"[green]✓[/green] Device paired: {device_id}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@devices_app.command("unpair")
def unpair_device(
    device_id: str = typer.Argument(..., help="Device ID"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
):
    """Unpair a device"""
    try:
        from .gateway_rpc_cli import GatewayRpcOpts, call_gateway_from_cli
        opts = GatewayRpcOpts(url=url, token=token, timeout=10_000)
        result = call_gateway_from_cli("device.unpair", opts, {"deviceId": device_id})
        console.print(f"[green]✓[/green] Device unpaired: {device_id}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@devices_app.callback(invoke_without_command=True)
def devices_default(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        list_devices()


__all__ = ["devices_app"]
