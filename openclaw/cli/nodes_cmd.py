"""Node/device management commands — mirrors TS src/cli/nodes-cli.ts"""
from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()
nodes_app = typer.Typer(help="Node and device management", no_args_is_help=True)

_DEFAULT_TIMEOUT_MS = 10_000
_DEFAULT_INVOKE_TIMEOUT_MS = 15_000
_DEFAULT_RUN_TIMEOUT_MS = 30_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rpc(method: str, params: dict, timeout_ms: int = _DEFAULT_TIMEOUT_MS,
         json_output: bool = False, url: Optional[str] = None, token: Optional[str] = None):
    from .gateway_rpc_cli import GatewayRpcOpts, call_gateway_from_cli
    opts = GatewayRpcOpts(url=url, token=token, timeout=timeout_ms, json_output=json_output)
    return call_gateway_from_cli(method, opts, params)


# ---------------------------------------------------------------------------
# Default callback — list nodes
# ---------------------------------------------------------------------------

@nodes_app.callback(invoke_without_command=True)
def nodes_default(ctx: typer.Context):
    """List nodes (default action)."""
    if ctx.invoked_subcommand is None:
        list_nodes_cmd(json_output=False, connected=False, url=None, token=None, timeout=_DEFAULT_TIMEOUT_MS)


# ---------------------------------------------------------------------------
# nodes list / nodes status
# ---------------------------------------------------------------------------

@nodes_app.command("list")
def list_nodes_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    connected: bool = typer.Option(False, "--connected", help="Only show connected nodes"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_MS, "--timeout", help="Timeout in ms"),
):
    """List paired nodes/devices"""
    try:
        params = {}
        if connected:
            params["connected"] = True
        result = _rpc("node.list", params, timeout_ms=timeout, json_output=json_output, url=url, token=token)

        items = result.get("nodes", result) if isinstance(result, dict) else result or []

        if json_output:
            console.print(json.dumps(items, indent=2, ensure_ascii=False))
            return

        if not items:
            console.print("[yellow]No paired nodes found[/yellow]")
            return

        table = Table(title="Nodes")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("IP", style="dim")
        table.add_column("Platform", style="dim")

        for node in (items if isinstance(items, list) else []):
            if isinstance(node, dict):
                connected_icon = "[green]●[/green]" if node.get("connected") else "[red]○[/red]"
                table.add_row(
                    node.get("id", ""),
                    node.get("name", ""),
                    connected_icon,
                    node.get("ip", ""),
                    node.get("platform", ""),
                )

        console.print(table)

    except Exception as e:
        from .gateway_rpc_cli import gateway_unreachable_message
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"\n{gateway_unreachable_message()}")
        raise typer.Exit(1)


@nodes_app.command("status")
def status_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    connected: bool = typer.Option(False, "--connected", help="Only show connected nodes"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_MS, "--timeout", help="Timeout in ms"),
):
    """Show nodes with connection status"""
    list_nodes_cmd(json_output=json_output, connected=connected, url=url, token=token, timeout=timeout)


# ---------------------------------------------------------------------------
# nodes describe
# ---------------------------------------------------------------------------

@nodes_app.command("describe")
def describe_cmd(
    node: str = typer.Option(..., "--node", help="Node ID, name, or IP"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_MS, "--timeout", help="Timeout in ms"),
):
    """Describe a node (capabilities and commands)"""
    try:
        result = _rpc("node.describe", {"node": node}, timeout_ms=timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if not result:
            console.print(f"[yellow]Node not found:[/yellow] {node}")
            raise typer.Exit(1)

        console.print(f"[bold]Node:[/bold] {result.get('name', node)}")
        console.print(f"  ID:       {result.get('id', '')}")
        console.print(f"  Platform: {result.get('platform', '')}")
        console.print(f"  Version:  {result.get('version', '')}")
        console.print(f"  Connected: {'yes' if result.get('connected') else 'no'}")

        capabilities = result.get("capabilities") or []
        if capabilities:
            console.print(f"\n[bold]Capabilities:[/bold]")
            for cap in capabilities:
                console.print(f"  • {cap}")

        commands = result.get("commands") or []
        if commands:
            console.print(f"\n[bold]Commands:[/bold]")
            for cmd in commands:
                name = cmd.get("name", "") if isinstance(cmd, dict) else cmd
                desc = cmd.get("description", "") if isinstance(cmd, dict) else ""
                console.print(f"  • {name}" + (f" — {desc}" if desc else ""))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# nodes pending
# ---------------------------------------------------------------------------

@nodes_app.command("pending")
def pending_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_MS, "--timeout", help="Timeout in ms"),
):
    """List pending pairing requests"""
    try:
        result = _rpc("node.pair.list", {}, timeout_ms=timeout,
                      json_output=json_output, url=url, token=token)

        pending = result.get("pending", result) if isinstance(result, dict) else result or []

        if json_output:
            console.print(json.dumps(pending, indent=2, ensure_ascii=False))
            return

        if not pending:
            console.print("[yellow]No pending pairing requests[/yellow]")
            return

        table = Table(title="Pending Pairing Requests")
        table.add_column("Request ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Platform", style="yellow")
        table.add_column("Created", style="dim")

        for req in (pending if isinstance(pending, list) else []):
            if isinstance(req, dict):
                table.add_row(
                    req.get("id", ""),
                    req.get("name", ""),
                    req.get("platform", ""),
                    req.get("createdAt", ""),
                )

        console.print(table)
        console.print(f"\nApprove with: [cyan]openclaw nodes approve <requestId>[/cyan]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# nodes approve / nodes reject
# ---------------------------------------------------------------------------

@nodes_app.command("approve")
def approve_cmd(
    request_id: str = typer.Argument(..., help="Pairing request ID"),
    name: Optional[str] = typer.Option(None, "--name", help="Friendly name for the node"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_MS, "--timeout", help="Timeout in ms"),
):
    """Approve a node pairing request"""
    try:
        params: dict = {"requestId": request_id}
        if name:
            params["name"] = name
        result = _rpc("node.pair.approve", params, timeout_ms=timeout, url=url, token=token)
        console.print(f"[green]✓[/green] Pairing request approved: {request_id}")
        if isinstance(result, dict) and result.get("nodeId"):
            console.print(f"  Node ID: {result['nodeId']}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@nodes_app.command("reject")
def reject_cmd(
    request_id: str = typer.Argument(..., help="Pairing request ID"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_MS, "--timeout", help="Timeout in ms"),
):
    """Reject a node pairing request"""
    try:
        result = _rpc("node.pair.reject", {"requestId": request_id}, timeout_ms=timeout, url=url, token=token)
        console.print(f"[green]✓[/green] Pairing request rejected: {request_id}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# nodes rename
# ---------------------------------------------------------------------------

@nodes_app.command("rename")
def rename_cmd(
    node: str = typer.Option(..., "--node", help="Node ID, name, or IP"),
    name: str = typer.Option(..., "--name", help="New name"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_MS, "--timeout", help="Timeout in ms"),
):
    """Rename a paired node"""
    try:
        result = _rpc("node.rename", {"node": node, "name": name}, timeout_ms=timeout, url=url, token=token)
        console.print(f"[green]✓[/green] Node renamed to: {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# nodes invoke
# ---------------------------------------------------------------------------

@nodes_app.command("invoke")
def invoke_cmd(
    node: str = typer.Option(..., "--node", help="Node ID, name, or IP"),
    command: str = typer.Option(..., "--command", help="Command to invoke"),
    params: Optional[str] = typer.Option(None, "--params", help="JSON params"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    invoke_timeout: int = typer.Option(_DEFAULT_INVOKE_TIMEOUT_MS, "--invoke-timeout", help="Node invoke timeout ms"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_TIMEOUT_MS, "--timeout", help="Transport timeout ms"),
):
    """Invoke a command on a paired node"""
    try:
        cmd_params = {}
        if params:
            try:
                cmd_params = json.loads(params)
            except json.JSONDecodeError as e:
                console.print(f"[red]Invalid JSON params:[/red] {e}")
                raise typer.Exit(1)

        rpc_params = {
            "node": node,
            "command": command,
            "params": cmd_params,
            "timeoutMs": invoke_timeout,
        }
        result = _rpc("node.invoke", rpc_params, timeout_ms=timeout + invoke_timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if isinstance(result, dict):
            if result.get("error"):
                console.print(f"[red]Error:[/red] {result['error']}")
                raise typer.Exit(1)
            output = result.get("output") or result.get("result") or result
            if isinstance(output, (dict, list)):
                console.print(json.dumps(output, indent=2, ensure_ascii=False))
            else:
                console.print(str(output))

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# nodes run (shell command on node)
# ---------------------------------------------------------------------------

@nodes_app.command("run")
def run_cmd(
    node: str = typer.Option(..., "--node", help="Node ID, name, or IP"),
    raw: str = typer.Option(..., "--raw", help="Raw shell command"),
    cwd: Optional[str] = typer.Option(None, "--cwd", help="Working directory"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    command_timeout: int = typer.Option(30_000, "--command-timeout", help="Command execution timeout ms"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_RUN_TIMEOUT_MS, "--timeout", help="Transport timeout ms"),
):
    """Run a shell command on a paired node"""
    try:
        invoke_params: dict = {
            "command": raw,
            "timeoutMs": command_timeout,
        }
        if cwd:
            invoke_params["cwd"] = cwd

        rpc_params = {
            "node": node,
            "command": "system.run",
            "params": invoke_params,
            "timeoutMs": command_timeout,
        }
        result = _rpc("node.invoke", rpc_params, timeout_ms=timeout + command_timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if isinstance(result, dict):
            if result.get("error"):
                console.print(f"[red]Error:[/red] {result['error']}")
                raise typer.Exit(1)
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            exit_code = result.get("exitCode", 0)
            if stdout:
                console.print(stdout, end="")
            if stderr:
                console.print(f"[red]{stderr}[/red]", end="")
            if exit_code != 0:
                raise typer.Exit(exit_code)
        else:
            console.print(str(result))

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# nodes notify
# ---------------------------------------------------------------------------

@nodes_app.command("notify")
def notify_cmd(
    node: str = typer.Option(..., "--node", help="Node ID, name, or IP"),
    title: str = typer.Option(..., "--title", help="Notification title"),
    body: Optional[str] = typer.Option(None, "--body", help="Notification body"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(_DEFAULT_INVOKE_TIMEOUT_MS, "--timeout", help="Timeout in ms"),
):
    """Send a notification to a node"""
    try:
        params = {
            "node": node,
            "command": "notification.send",
            "params": {"title": title, "body": body or ""},
            "timeoutMs": timeout,
        }
        result = _rpc("node.invoke", params, timeout_ms=timeout + 5000, url=url, token=token)
        console.print(f"[green]✓[/green] Notification sent to: {node}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
