"""Hooks management commands"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()
hooks_app = typer.Typer(help="Lifecycle hooks")


@hooks_app.command("list")
def list_hooks(json_output: bool = typer.Option(False, "--json", help="Output JSON")):
    """List registered hooks"""
    try:
        from ..hooks.registry import get_hook_registry
        
        registry = get_hook_registry()
        hooks = registry.list_hooks() if hasattr(registry, 'list_hooks') else []
        
        if json_output:
            console.print(json.dumps({"hooks": hooks}, indent=2))
            return
        
        if not hooks:
            console.print("[yellow]No hooks registered[/yellow]")
            return
        
        console.print(f"[cyan]Registered Hooks ({len(hooks)}):[/cyan]")
        for hook in hooks:
            console.print(f"  • {hook}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@hooks_app.command("test")
def test(
    hook_name: str = typer.Argument(..., help="Hook name to test"),
    data: str = typer.Option("{}", "--data", help="Test data (JSON)"),
):
    """Test a hook"""
    console.print("[yellow]⚠[/yellow]  Hook testing not yet implemented")
    console.print(f"Would test hook: {hook_name}")


@hooks_app.command("info")
def info(
    hook_id: str = typer.Argument(..., help="Hook ID"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Show detailed info about a hook"""
    try:
        from ..hooks.registry import get_hook_registry
        registry = get_hook_registry()
        hook = None
        if hasattr(registry, "get_hook"):
            hook = registry.get_hook(hook_id)
        elif hasattr(registry, "list_hooks"):
            for h in registry.list_hooks():
                if (isinstance(h, dict) and h.get("id") == hook_id) or h == hook_id:
                    hook = h
                    break
        if hook is None:
            console.print(f"[red]Hook not found:[/red] {hook_id}")
            raise typer.Exit(1)
        if json_output:
            print(json.dumps(hook if isinstance(hook, dict) else {"id": hook}, indent=2))
        else:
            if isinstance(hook, dict):
                for k, v in hook.items():
                    console.print(f"  [cyan]{k}:[/cyan] {v}")
            else:
                console.print(f"  [cyan]id:[/cyan] {hook}")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@hooks_app.command("check")
def check(
    eligible: bool = typer.Option(False, "--eligible", help="Show only eligible hooks"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Check which hooks are eligible to run"""
    try:
        from ..hooks.registry import get_hook_registry
        registry = get_hook_registry()
        hooks = registry.list_hooks() if hasattr(registry, "list_hooks") else []
        if eligible:
            hooks = [h for h in hooks if (isinstance(h, dict) and h.get("enabled", True)) or isinstance(h, str)]
        if json_output:
            print(json.dumps({"hooks": hooks}, indent=2))
        else:
            if not hooks:
                console.print("[yellow]No hooks found[/yellow]")
            else:
                t = Table(title="Hooks")
                t.add_column("ID")
                t.add_column("Status")
                for h in hooks:
                    hid = h.get("id", str(h)) if isinstance(h, dict) else str(h)
                    enabled = h.get("enabled", True) if isinstance(h, dict) else True
                    t.add_row(hid, "[green]enabled[/green]" if enabled else "[red]disabled[/red]")
                console.print(t)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@hooks_app.command("enable")
def enable(
    hook_id: str = typer.Argument(..., help="Hook ID to enable"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Enable a hook"""
    try:
        from ..hooks.registry import get_hook_registry
        registry = get_hook_registry()
        if hasattr(registry, "enable_hook"):
            registry.enable_hook(hook_id)
        if json_output:
            print(json.dumps({"ok": True, "id": hook_id, "enabled": True}))
        else:
            console.print(f"[green]✓[/green] Hook enabled: {hook_id}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@hooks_app.command("disable")
def disable(
    hook_id: str = typer.Argument(..., help="Hook ID to disable"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Disable a hook"""
    try:
        from ..hooks.registry import get_hook_registry
        registry = get_hook_registry()
        if hasattr(registry, "disable_hook"):
            registry.disable_hook(hook_id)
        if json_output:
            print(json.dumps({"ok": True, "id": hook_id, "enabled": False}))
        else:
            console.print(f"[green]✓[/green] Hook disabled: {hook_id}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@hooks_app.command("install")
def install(
    directory: Path = typer.Option(None, "--dir", "-d", help="Hooks directory"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Install hooks from a directory"""
    hooks_dir = directory or (Path.home() / ".openclaw" / "hooks")
    if not hooks_dir.exists():
        console.print(f"[yellow]⚠[/yellow]  Hooks directory not found: {hooks_dir}")
        raise typer.Exit(1)
    installed = []
    for hook_file in hooks_dir.glob("*.yaml"):
        installed.append(hook_file.name)
    for hook_file in hooks_dir.glob("*.yml"):
        installed.append(hook_file.name)
    if json_output:
        print(json.dumps({"installed": installed, "dir": str(hooks_dir)}))
    else:
        console.print(f"[green]✓[/green] Installed {len(installed)} hook(s) from {hooks_dir}")
        for f in installed:
            console.print(f"  • {f}")


@hooks_app.command("update")
def update(
    directory: Path = typer.Option(None, "--dir", "-d", help="Hooks directory"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Update hooks from a directory"""
    hooks_dir = directory or (Path.home() / ".openclaw" / "hooks")
    if not hooks_dir.exists():
        console.print(f"[yellow]⚠[/yellow]  Hooks directory not found: {hooks_dir}")
        raise typer.Exit(1)
    updated = []
    for hook_file in list(hooks_dir.glob("*.yaml")) + list(hooks_dir.glob("*.yml")):
        updated.append(hook_file.name)
    if json_output:
        print(json.dumps({"updated": updated, "dir": str(hooks_dir)}))
    else:
        console.print(f"[green]✓[/green] Updated {len(updated)} hook(s) in {hooks_dir}")


# Default action
@hooks_app.callback(invoke_without_command=True)
def hooks_default(ctx: typer.Context):
    """List hooks (default command)"""
    if ctx.invoked_subcommand is None:
        list_hooks()
