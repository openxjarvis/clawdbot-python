"""Agent execution and management commands — mirrors TS src/cli/program/register.agent.ts"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..config.loader import load_config

console = Console()
agent_app = typer.Typer(help="Agent execution and management", no_args_is_help=True)

# Create agents subcommand group
agents_app = typer.Typer(help="Manage isolated agents")
agent_app.add_typer(agents_app, name="agents")


@agent_app.command("run")
def run(
    message: str = typer.Option(..., "--message", "-m", help="Message for the agent"),
    to: str = typer.Option(None, "--to", "-t", help="Recipient number"),
    session_id: str = typer.Option(None, "--session-id", help="Explicit session id"),
    agent_id: str = typer.Option(None, "--agent", help="Agent id"),
    thinking: str = typer.Option(None, "--thinking", help="Thinking level (off|low|medium|high)"),
    channel: str = typer.Option(None, "--channel", help="Delivery channel"),
    deliver: bool = typer.Option(False, "--deliver", help="Send reply back to channel"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    timeout: int = typer.Option(600, "--timeout", help="Timeout in seconds"),
):
    """Run an agent turn via the Gateway"""
    import asyncio
    import uuid
    from ..gateway.rpc_client import GatewayRPCClient
    
    try:
        # Generate session ID if not provided
        if not session_id:
            session_id = f"cli-{uuid.uuid4().hex[:8]}"
        
        # Create RPC client
        config = load_config()
        client = GatewayRPCClient(config=config)
        
        # Prepare parameters
        params = {
            "message": message,
            "sessionId": session_id,
        }
        
        if agent_id:
            params["agentId"] = agent_id
        if thinking:
            params["thinking"] = thinking
        if channel:
            params["channel"] = channel
        if to:
            params["to"] = to
        
        # Execute agent turn
        console.print(f"[cyan]→[/cyan] Running agent (session: {session_id})...")
        
        result = asyncio.run(client.call_agent_turn(
            message=message,
            session_id=session_id,
            agent_id=agent_id,
            thinking=thinking,
            timeout=timeout,
        ))
        
        if json_output:
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            return
        
        # Display response
        if result.get("error"):
            console.print(f"[red]Error:[/red] {result['error']}")
            raise typer.Exit(1)
        
        response = result.get("response", {})
        
        # Display assistant message
        if "text" in response:
            console.print("\n[green]Assistant:[/green]")
            console.print(response["text"])
        
        # Display tool calls if any
        if "toolCalls" in response and response["toolCalls"]:
            console.print("\n[yellow]Tool Calls:[/yellow]")
            for tool_call in response["toolCalls"]:
                console.print(f"  • {tool_call.get('name', 'unknown')}")
        
        # Display usage if available
        if "usage" in result:
            usage = result["usage"]
            console.print(f"\n[dim]Tokens: {usage.get('totalTokens', 0)} | Cost: ${usage.get('cost', 0):.4f}[/dim]")
        
    except ConnectionError as e:
        console.print(f"[red]Connection Error:[/red] Gateway not running on configured port")
        console.print(f"Please start the gateway: [cyan]openclaw gateway run[/cyan]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if "--verbose" in typer.get_app_dir("openclaw"):
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@agents_app.command("list")
def list_agents(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    bindings: bool = typer.Option(False, "--bindings", help="Include routing bindings"),
):
    """List configured agents"""
    try:
        config = load_config()
        
        if not config.agents or not config.agents.agents:
            console.print("[yellow]No agents configured[/yellow]")
            return
        
        if json_output:
            agents_data = [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "workspace": agent.workspace,
                }
                for agent in config.agents.agents
            ]
            console.print(json.dumps(agents_data, indent=2))
            return
        
        table = Table(title="Configured Agents")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Workspace", style="yellow")
        
        for agent in config.agents.agents:
            table.add_row(
                agent.id,
                agent.name or "-",
                agent.workspace or "-",
            )
        
        console.print(table)
    
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@agents_app.command("add")
def add(
    name: Optional[str] = typer.Argument(None, help="Agent name"),
    workspace: Optional[str] = typer.Option(None, "--workspace", help="Workspace directory"),
    model: Optional[str] = typer.Option(None, "--model", help="Model id"),
    agent_dir: Optional[str] = typer.Option(None, "--agent-dir", help="Agent state directory"),
    bind: Optional[list[str]] = typer.Option(None, "--bind", help="Channel binding spec (repeatable)"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Disable prompts"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Add a new isolated agent"""
    try:
        from ..config.loader import write_config_file
        from ..config.paths import resolve_config_path

        raw = _load_raw_config()

        # Resolve agent name / id
        agent_name = name
        if not agent_name and not non_interactive:
            agent_name = typer.prompt("Agent name")
        if not agent_name:
            console.print("[red]Error:[/red] Agent name is required")
            raise typer.Exit(1)

        # Normalize agent id (lowercase, hyphens)
        import re
        agent_id = re.sub(r"[^a-z0-9-]", "-", agent_name.lower().strip()).strip("-") or agent_name.lower()
        if agent_id == "default":
            console.print('[red]Error:[/red] "default" is a reserved agent id')
            raise typer.Exit(1)

        # Check for duplicates
        agents_list = _get_agents_list(raw)
        if any(a.get("id") == agent_id for a in agents_list if isinstance(a, dict)):
            console.print(f"[red]Error:[/red] Agent '{agent_id}' already exists")
            raise typer.Exit(1)

        # Resolve workspace directory
        ws = workspace
        if not ws and not non_interactive:
            ws = typer.prompt("Workspace directory (leave blank for auto)", default="")
        if not ws:
            ws = str(Path.home() / ".openclaw" / "workspaces" / agent_id)

        ws = str(Path(ws).expanduser().resolve())

        # Ensure workspace exists
        Path(ws).mkdir(parents=True, exist_ok=True)

        # Build new agent entry
        new_agent: dict = {
            "id": agent_id,
            "name": agent_name,
            "workspace": ws,
        }
        if model:
            new_agent["model"] = model
        if agent_dir:
            new_agent["agentDir"] = str(Path(agent_dir).expanduser().resolve())

        # Apply bindings
        if bind:
            bindings = []
            for b in bind:
                parts = b.split(":", 1)
                binding: dict = {"channel": parts[0]}
                if len(parts) > 1:
                    binding["accountId"] = parts[1]
                bindings.append(binding)
            new_agent["bindings"] = bindings

        # Add to config
        if "agents" not in raw or not isinstance(raw.get("agents"), dict):
            raw["agents"] = {}
        if "agents" not in raw["agents"] or not isinstance(raw["agents"].get("agents"), list):
            raw["agents"]["agents"] = []
        raw["agents"]["agents"].append(new_agent)

        write_config_file(raw)

        if json_output:
            console.print(json.dumps(new_agent, indent=2))
            return

        console.print(f"[green]✓[/green] Agent created: [cyan]{agent_id}[/cyan]")
        console.print(f"  Name:      {agent_name}")
        console.print(f"  Workspace: {ws}")
        if model:
            console.print(f"  Model:     {model}")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@agents_app.command("delete")
def delete(
    agent_id: str = typer.Argument(..., help="Agent id to delete"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Delete an agent and prune its workspace/state"""
    try:
        from ..config.loader import write_config_file

        raw = _load_raw_config()
        agents_list = _get_agents_list(raw)
        idx = next((i for i, a in enumerate(agents_list) if isinstance(a, dict) and a.get("id") == agent_id), -1)
        if idx < 0:
            console.print(f"[red]Agent not found:[/red] {agent_id}")
            raise typer.Exit(1)

        agent_entry = agents_list[idx]
        workspace = agent_entry.get("workspace", "") if isinstance(agent_entry, dict) else ""

        if not force:
            confirm = typer.confirm(f"Delete agent '{agent_id}'?", default=False)
            if not confirm:
                console.print("Cancelled")
                return

        # Remove from list
        raw["agents"]["agents"] = [a for i, a in enumerate(agents_list) if i != idx]
        write_config_file(raw)

        if json_output:
            console.print(json.dumps({"deleted": agent_id, "workspace": workspace}))
            return

        console.print(f"[green]✓[/green] Agent deleted: [cyan]{agent_id}[/cyan]")
        if workspace:
            console.print(f"[dim]  Workspace at {workspace} was not removed (manual cleanup needed)[/dim]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@agents_app.command("set-identity")
def set_identity(
    agent_id: Optional[str] = typer.Option(None, "--agent", help="Agent id to update"),
    workspace: Optional[str] = typer.Option(None, "--workspace", help="Workspace directory (resolves agent)"),
    name: Optional[str] = typer.Option(None, "--name", help="Identity name"),
    theme: Optional[str] = typer.Option(None, "--theme", help="Identity theme"),
    emoji: Optional[str] = typer.Option(None, "--emoji", help="Identity emoji"),
    avatar: Optional[str] = typer.Option(None, "--avatar", help="Identity avatar"),
    from_identity: bool = typer.Option(False, "--from-identity", help="Read values from IDENTITY.md"),
    identity_file: Optional[str] = typer.Option(None, "--identity-file", help="Explicit IDENTITY.md path"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Update an agent identity (writes to IDENTITY.md in agent workspace)"""
    try:
        from ..config.loader import write_config_file

        raw = _load_raw_config()
        agents_list = _get_agents_list(raw)

        # Resolve which agent to update
        target_id = agent_id
        if not target_id and workspace:
            # Find agent by workspace path
            ws_resolved = str(Path(workspace).expanduser().resolve())
            for a in agents_list:
                if isinstance(a, dict):
                    a_ws = a.get("workspace", "")
                    if a_ws and str(Path(a_ws).expanduser().resolve()) == ws_resolved:
                        target_id = a.get("id")
                        break

        if not target_id:
            # Default to first agent or prompt
            if agents_list:
                target_id = agents_list[0].get("id") if isinstance(agents_list[0], dict) else None
            if not target_id:
                console.print("[red]Error:[/red] No agent found. Use --agent <id>")
                raise typer.Exit(1)

        agent_entry = next((a for a in agents_list if isinstance(a, dict) and a.get("id") == target_id), None)
        if not agent_entry:
            console.print(f"[red]Agent not found:[/red] {target_id}")
            raise typer.Exit(1)

        # Resolve IDENTITY.md path
        if identity_file:
            identity_path = Path(identity_file).expanduser()
        else:
            ws = agent_entry.get("workspace") or str(Path.home() / ".openclaw" / "workspaces" / target_id)
            identity_path = Path(ws) / "IDENTITY.md"

        updated: dict = {}

        # Read existing identity
        existing_content = ""
        if identity_path.exists():
            existing_content = identity_path.read_text(encoding="utf-8")

        if from_identity and identity_path.exists():
            # Parse existing values (simple key: value format)
            for line in existing_content.splitlines():
                if ": " in line:
                    k, v = line.split(": ", 1)
                    k_lower = k.strip().lower()
                    if k_lower == "name" and not name:
                        name = v.strip()
                    elif k_lower == "theme" and not theme:
                        theme = v.strip()
                    elif k_lower == "emoji" and not emoji:
                        emoji = v.strip()
                    elif k_lower == "avatar" and not avatar:
                        avatar = v.strip()

        # Build IDENTITY.md content
        lines = []
        if name:
            lines.append(f"# {name}")
            updated["name"] = name
        if emoji:
            lines.append(f"\nEmoji: {emoji}")
            updated["emoji"] = emoji
        if theme:
            lines.append(f"Theme: {theme}")
            updated["theme"] = theme
        if avatar:
            lines.append(f"Avatar: {avatar}")
            updated["avatar"] = avatar

        if lines:
            identity_path.parent.mkdir(parents=True, exist_ok=True)
            identity_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            console.print(f"[green]✓[/green] Identity updated for [cyan]{target_id}[/cyan]")
            console.print(f"  Written to: {identity_path}")
        else:
            console.print("[yellow]⚠[/yellow]  No identity fields provided (use --name, --emoji, --theme, --avatar)")

        if json_output:
            console.print(json.dumps({**updated, "agentId": target_id, "path": str(identity_path)}))

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_raw_config() -> dict:
    from pathlib import Path as _Path
    from ..config.loader import load_config_raw
    from ..config.paths import resolve_config_path
    try:
        cfg_path = resolve_config_path()
        if cfg_path and _Path(cfg_path).exists():
            return load_config_raw(_Path(cfg_path)) or {}
    except Exception:
        pass
    default = _Path.home() / ".openclaw" / "openclaw.json"
    if default.exists():
        try:
            return load_config_raw(default) or {}
        except Exception:
            pass
    return {}


def _get_agents_list(raw: dict) -> list:
    agents_section = raw.get("agents") or {}
    if isinstance(agents_section, dict):
        return agents_section.get("agents") or []
    return []
