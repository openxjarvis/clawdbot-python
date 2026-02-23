"""Message sending and channel actions — mirrors TS outbound send commands"""
from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console

console = Console()
message_app = typer.Typer(help="Send messages and channel actions", no_args_is_help=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rpc(method: str, params: dict, timeout_ms: int = 10_000,
         json_output: bool = False, url: Optional[str] = None, token: Optional[str] = None):
    from .gateway_rpc_cli import GatewayRpcOpts, call_gateway_from_cli
    opts = GatewayRpcOpts(url=url, token=token, timeout=timeout_ms, json_output=json_output)
    return call_gateway_from_cli(method, opts, params)


# ---------------------------------------------------------------------------
# message send
# ---------------------------------------------------------------------------

@message_app.command("send")
def send(
    target: str = typer.Option(..., "--target", help="Target (phone number, user id, chat id)"),
    message: str = typer.Option(..., "--message", "-m", help="Message text"),
    channel: Optional[str] = typer.Option(None, "--channel", help="Channel (telegram|discord|whatsapp|etc)"),
    account: Optional[str] = typer.Option(None, "--account", help="Account id"),
    media: Optional[str] = typer.Option(None, "--media", help="Media file path"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(15_000, "--timeout", help="Timeout in ms"),
):
    """Send a text message via a channel"""
    try:
        params: dict = {
            "target": target,
            "text": message,
        }
        if channel:
            params["channel"] = channel
        if account:
            params["accountId"] = account
        if media:
            params["media"] = media

        result = _rpc("message.outbound.send", params, timeout_ms=timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if isinstance(result, dict) and result.get("messageId"):
            console.print(f"[green]✓[/green] Message sent (id: {result['messageId']})")
        else:
            console.print(f"[green]✓[/green] Message sent to {target}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# message broadcast
# ---------------------------------------------------------------------------

@message_app.command("broadcast")
def broadcast(
    targets: list[str] = typer.Argument(..., help="Target list"),
    message: str = typer.Option(..., "--message", "-m", help="Message text"),
    channel: Optional[str] = typer.Option(None, "--channel", help="Channel"),
    account: Optional[str] = typer.Option(None, "--account", help="Account id"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(30_000, "--timeout", help="Timeout in ms"),
):
    """Broadcast message to multiple targets"""
    try:
        params: dict = {
            "targets": list(targets),
            "text": message,
        }
        if channel:
            params["channel"] = channel
        if account:
            params["accountId"] = account

        result = _rpc("message.outbound.broadcast", params, timeout_ms=timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if isinstance(result, dict):
            sent = result.get("sent", len(targets))
            failed = result.get("failed", 0)
            console.print(f"[green]✓[/green] Broadcast sent: {sent}/{len(targets)} targets")
            if failed:
                console.print(f"[yellow]  {failed} failed[/yellow]")
        else:
            console.print(f"[green]✓[/green] Broadcast sent to {len(targets)} targets")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# message poll
# ---------------------------------------------------------------------------

@message_app.command("poll")
def poll(
    poll_question: str = typer.Option(..., "--poll-question", help="Poll question"),
    poll_option: list[str] = typer.Option(..., "--poll-option", help="Poll option (repeatable)"),
    channel: str = typer.Option(..., "--channel", help="Channel"),
    target: str = typer.Option(..., "--target", help="Target channel/group"),
    account: Optional[str] = typer.Option(None, "--account", help="Account id"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(10_000, "--timeout", help="Timeout in ms"),
):
    """Create a poll"""
    try:
        params: dict = {
            "channel": channel,
            "target": target,
            "question": poll_question,
            "options": list(poll_option),
        }
        if account:
            params["accountId"] = account

        result = _rpc("message.poll.create", params, timeout_ms=timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        console.print(f"[green]✓[/green] Poll created: {poll_question}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# message react
# ---------------------------------------------------------------------------

@message_app.command("react")
def react(
    message_id: str = typer.Option(..., "--message-id", help="Message id"),
    emoji: str = typer.Option(..., "--emoji", help="Emoji reaction"),
    channel: str = typer.Option(..., "--channel", help="Channel"),
    target: str = typer.Option(..., "--target", help="Target channel/group"),
    account: Optional[str] = typer.Option(None, "--account", help="Account id"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(10_000, "--timeout", help="Timeout in ms"),
):
    """React to a message"""
    try:
        params: dict = {
            "messageId": message_id,
            "emoji": emoji,
            "channel": channel,
            "target": target,
        }
        if account:
            params["accountId"] = account

        result = _rpc("message.react", params, timeout_ms=timeout, url=url, token=token)
        console.print(f"[green]✓[/green] Reacted with {emoji} to message {message_id}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# message read / edit / delete
# ---------------------------------------------------------------------------

@message_app.command("read")
def read(
    message_id: str = typer.Argument(..., help="Message id"),
    channel: str = typer.Option(..., "--channel", help="Channel"),
    target: str = typer.Option(..., "--target", help="Target"),
    account: Optional[str] = typer.Option(None, "--account", help="Account id"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(10_000, "--timeout", help="Timeout in ms"),
):
    """Mark a message as read"""
    try:
        params: dict = {
            "messageId": message_id,
            "channel": channel,
            "target": target,
        }
        if account:
            params["accountId"] = account

        result = _rpc("message.read", params, timeout_ms=timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            console.print(f"[green]✓[/green] Marked as read: {message_id}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@message_app.command("edit")
def edit(
    message_id: str = typer.Argument(..., help="Message id"),
    message: str = typer.Option(..., "--message", "-m", help="New message text"),
    channel: str = typer.Option(..., "--channel", help="Channel"),
    target: str = typer.Option(..., "--target", help="Target"),
    account: Optional[str] = typer.Option(None, "--account", help="Account id"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(10_000, "--timeout", help="Timeout in ms"),
):
    """Edit a message"""
    try:
        params: dict = {
            "messageId": message_id,
            "text": message,
            "channel": channel,
            "target": target,
        }
        if account:
            params["accountId"] = account

        result = _rpc("message.edit", params, timeout_ms=timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            console.print(f"[green]✓[/green] Message edited: {message_id}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@message_app.command("delete")
def delete(
    message_id: str = typer.Argument(..., help="Message id"),
    channel: str = typer.Option(..., "--channel", help="Channel"),
    target: str = typer.Option(..., "--target", help="Target"),
    account: Optional[str] = typer.Option(None, "--account", help="Account id"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    url: Optional[str] = typer.Option(None, "--url", help="Gateway WebSocket URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Gateway auth token"),
    timeout: int = typer.Option(10_000, "--timeout", help="Timeout in ms"),
):
    """Delete a message"""
    try:
        params: dict = {
            "messageId": message_id,
            "channel": channel,
            "target": target,
        }
        if account:
            params["accountId"] = account

        result = _rpc("message.delete", params, timeout_ms=timeout,
                      json_output=json_output, url=url, token=token)

        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            console.print(f"[green]✓[/green] Message deleted: {message_id}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
