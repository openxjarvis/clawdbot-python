"""Security and permissions commands"""

from typing import Optional

import typer
from rich.console import Console

console = Console()
security_app = typer.Typer(help="Security and permissions")


@security_app.command("status")
def status(json_output: bool = typer.Option(False, "--json", help="Output JSON")):
    """Show current permission level and security settings"""
    from ..config.loader import load_config
    from ..wizard.permission_presets import detect_preset_level, PRESETS, PRESET_ORDER

    try:
        config = load_config()
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(1)

    exec_cfg = config.tools.exec if (config.tools and config.tools.exec) else None
    security = exec_cfg.security if exec_cfg else "deny"
    safe_bins = exec_cfg.safe_bins if exec_cfg else []
    ask = exec_cfg.ask if exec_cfg else "on-miss"

    channels = config.channels
    channel_policies: dict[str, dict] = {}
    if channels:
        for attr in ("telegram", "feishu", "discord", "whatsapp", "slack"):
            ch = getattr(channels, attr, None)
            if ch and getattr(ch, "enabled", False):
                dm = getattr(ch, "dmPolicy", None) or getattr(ch, "dm_policy", "pairing") or "pairing"
                gp = getattr(ch, "groupPolicy", None) or getattr(ch, "group_policy", "allowlist") or "allowlist"
                channel_policies[attr] = {"dmPolicy": dm, "groupPolicy": gp}

    # Outbound crossContext settings
    msg_cfg = config.tools.message if (config.tools and config.tools.message) else None
    cc = msg_cfg.cross_context if msg_cfg else None
    allow_within = cc.allow_within_provider if (cc and cc.allow_within_provider is not None) else True
    allow_across = cc.allow_across_providers if (cc and cc.allow_across_providers is not None) else False

    current_preset = detect_preset_level(config)

    if json_output:
        import json
        print(json.dumps({
            "preset": current_preset,
            "exec_security": security,
            "exec_ask": ask,
            "safe_bins": safe_bins,
            "channel_policies": channel_policies,
            "outbound": {
                "allowWithinProvider": allow_within,
                "allowAcrossProviders": allow_across,
            },
        }, indent=2))
        return

    # Rich display
    console.print()
    if current_preset:
        p = PRESETS[current_preset]
        idx = PRESET_ORDER.index(current_preset) + 1
        console.print(
            f"[bold green]Permission level:[/bold green] "
            f"[bold]{idx}. {p['label']}[/bold]  — {p['tagline']}"
        )
    else:
        console.print("[bold yellow]Permission level:[/bold yellow] custom (does not match any preset)")

    console.print()
    console.print("[bold]Execution:[/bold]")
    console.print(f"  [cyan]exec.security[/cyan]  : [bold]{security}[/bold]")
    console.print(f"  [cyan]exec.ask[/cyan]       : {ask}")
    if safe_bins:
        console.print(f"  [cyan]safe_bins[/cyan]      : {', '.join(safe_bins)}")

    if channel_policies:
        console.print()
        console.print("[bold]Inbound (入站):[/bold]")
        for ch_name, policies in channel_policies.items():
            console.print(f"  [cyan]{ch_name}.dmPolicy[/cyan]   : {policies['dmPolicy']}")
            console.print(f"  [cyan]{ch_name}.groupPolicy[/cyan]: {policies['groupPolicy']}")

    console.print()
    console.print("[bold]Outbound (出站):[/bold]")
    console.print(f"  [cyan]message.crossContext.allowWithinProvider[/cyan] : [bold]{allow_within}[/bold]")
    console.print(f"  [cyan]message.crossContext.allowAcrossProviders[/cyan]: [bold]{allow_across}[/bold]")

    console.print()
    console.print(
        "Change level: [bold]uv run openclaw security preset[/bold]  "
        "or  [bold]openclaw security preset <level>[/bold]"
    )
    console.print()


@security_app.command("preset")
def preset(
    level: Optional[str] = typer.Argument(
        None,
        help="Permission level: relaxed | trusted | standard | strict",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Set the permission level (relaxed / trusted / standard / strict)

    Run without arguments for an interactive menu.
    """
    from ..config.loader import load_config, save_config
    from ..wizard.permission_presets import (
        display_presets_menu, detect_preset_level, apply_preset,
        PRESET_ORDER, PRESETS, DEFAULT_PRESET,
    )

    try:
        config = load_config()
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(1)

    current = detect_preset_level(config)

    # If no level given, show interactive menu
    if level is None:
        display_presets_menu(current)
        default_key = current or DEFAULT_PRESET
        default_num = PRESET_ORDER.index(default_key) + 1
        while True:
            raw = input(
                f"Select [1-{len(PRESET_ORDER)}] (default {default_num} = {PRESETS[default_key]['label']}): "
            ).strip()
            if not raw:
                level = default_key
                break
            if raw.isdigit() and 1 <= int(raw) <= len(PRESET_ORDER):
                level = PRESET_ORDER[int(raw) - 1]
                break
            if raw.lower() in PRESET_ORDER:
                level = raw.lower()
                break
            console.print(f"  [red]Invalid.[/red] Enter 1–{len(PRESET_ORDER)} or a preset name.")
    else:
        level = level.lower()
        if level not in PRESET_ORDER:
            console.print(
                f"[red]Unknown preset:[/red] {level!r}. "
                f"Choose from: {', '.join(PRESET_ORDER)}"
            )
            raise typer.Exit(1)

    if level == current and not yes:
        console.print(f"[green]✓[/green] Already set to [bold]{PRESETS[level]['label']}[/bold] — no changes needed.")
        raise typer.Exit(0)

    p = PRESETS[level]
    console.print()
    console.print(f"[bold]Applying: {p['label']}[/bold]  — {p['tagline']}")
    console.print()
    console.print("  [bold]Execution:[/bold]")
    console.print(f"    exec.security → [bold]{p['exec_security']}[/bold]")
    if p["safe_bins"]:
        console.print(f"    safe_bins     → {', '.join(p['safe_bins'])}")
    console.print()
    console.print("  [bold]Inbound (入站):[/bold]")
    console.print(f"    dmPolicy      → [bold]{p['dm_policy']}[/bold]")
    console.print(f"    groupPolicy   → [bold]{p['group_policy']}[/bold]")
    console.print()
    console.print("  [bold]Outbound (出站):[/bold]")
    console.print(f"    allowWithinProvider  → [bold]{p['allow_within_provider']}[/bold]")
    console.print(f"    allowAcrossProviders → [bold]{p['allow_across_providers']}[/bold]")
    console.print()

    if not yes:
        confirm = input("Apply these changes? [Y/n]: ").strip().lower()
        if confirm not in ("", "y", "yes"):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    config = apply_preset(config, level)
    save_config(config)
    console.print(f"[green]✓[/green] Permission level set to [bold]{p['label']}[/bold].")
    console.print("  Restart openclaw for changes to take effect: [bold]uv run openclaw start[/bold]")
    console.print()


@security_app.command("audit")
def audit(
    deep: bool = typer.Option(False, "--deep", help="Deep scan"),
    fix: bool = typer.Option(False, "--fix", help="Apply security fixes"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Run security audit"""
    from pathlib import Path
    from ..config.loader import load_config, get_config_path, save_config
    
    console.print("[cyan]Running security audit...[/cyan]\n")
    
    results = {
        "critical": [],
        "warnings": [],
        "info": [],
    }
    
    # Check 1: Config file permissions
    config_file = get_config_path()
    if config_file.exists():
        import stat
        st = config_file.stat()
        file_mode = st.st_mode & 0o777
        
        # Check if file is readable by others
        if file_mode & 0o077:
            results["warnings"].append({
                "check": "config_permissions",
                "message": f"Config file {config_file} has weak permissions: {oct(file_mode)}",
                "fix": f"chmod 600 {config_file}",
            })
            console.print(f"[yellow]⚠[/yellow]  Config file has weak permissions: {oct(file_mode)}")
            
            if fix:
                try:
                    config_file.chmod(0o600)
                    console.print(f"[green]✓[/green] Fixed: Set permissions to 600")
                except Exception as e:
                    console.print(f"[red]Error:[/red] Could not fix permissions: {e}")
        else:
            console.print(f"[green]✓[/green] Config file permissions OK: {oct(file_mode)}")
    
    # Check 2: Gateway authentication
    try:
        config = load_config()
        
        if config.gateway and config.gateway.auth:
            auth_mode = config.gateway.auth.mode
            
            if auth_mode == "none":
                results["critical"].append({
                    "check": "gateway_auth",
                    "message": "Gateway has no authentication",
                    "fix": "Configure token or password auth: openclaw configure --section gateway",
                })
                console.print("[red]✗[/red] Gateway has no authentication")
            elif auth_mode == "token":
                token = config.gateway.auth.token
                if not token:
                    results["critical"].append({
                        "check": "gateway_token",
                        "message": "Gateway token not set",
                        "fix": "Generate token: openclaw gateway generate-token",
                    })
                    console.print("[red]✗[/red] Gateway token not set")
                elif len(token) < 32:
                    results["warnings"].append({
                        "check": "gateway_token",
                        "message": "Gateway token is weak (< 32 characters)",
                        "fix": "Generate strong token: openclaw gateway generate-token",
                    })
                    console.print("[yellow]⚠[/yellow]  Gateway token is weak")
                else:
                    console.print("[green]✓[/green] Gateway token is secure")
            elif auth_mode == "password":
                password = config.gateway.auth.password
                if not password:
                    results["critical"].append({
                        "check": "gateway_password",
                        "message": "Gateway password not set",
                        "fix": "Set password: openclaw configure --section gateway",
                    })
                    console.print("[red]✗[/red] Gateway password not set")
                elif len(password) < 12:
                    results["warnings"].append({
                        "check": "gateway_password",
                        "message": "Gateway password is weak (< 12 characters)",
                        "fix": "Set stronger password: openclaw configure --section gateway",
                    })
                    console.print("[yellow]⚠[/yellow]  Gateway password is weak")
                else:
                    console.print("[green]✓[/green] Gateway password is secure")
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
    
    # Check 3: Channel DM policies
    try:
        config = load_config()
        
        for channel_name in ["telegram", "discord", "slack"]:
            channel_cfg = getattr(config.channels, channel_name, None)
            if channel_cfg and channel_cfg.get("enabled"):
                dm_policy = channel_cfg.get("dmPolicy") or channel_cfg.get("dm_policy", "open")
                
                if dm_policy == "open":
                    results["warnings"].append({
                        "check": f"{channel_name}_dm_policy",
                        "message": f"{channel_name.title()} has open DM policy",
                        "fix": f"Set dmPolicy to 'pairing' or 'allowlist' in config",
                    })
                    console.print(f"[yellow]⚠[/yellow]  {channel_name.title()} has open DM policy")
                else:
                    console.print(f"[green]✓[/green] {channel_name.title()} DM policy: {dm_policy}")
    except Exception:
        pass
    
    # Check 4: Bash execution security (deep scan)
    if deep:
        console.print("\n[cyan]Deep scan...[/cyan]")
        
        try:
            config = load_config()
            
            if config.tools and config.tools.exec:
                security_mode = config.tools.exec.security
                
                if security_mode == "full":
                    results["info"].append({
                        "check": "bash_security",
                        "message": "Bash execution has full access",
                        "info": "This is powerful but can be risky. Consider 'allowlist' mode.",
                    })
                    console.print("[cyan]ℹ[/cyan]  Bash execution: full access (powerful but risky)")
                elif security_mode == "deny":
                    console.print("[green]✓[/green] Bash execution: denied")
                else:
                    console.print(f"[green]✓[/green] Bash execution: {security_mode}")
        except Exception:
            pass
    
    # Check 5: API keys in config (deep scan)
    if deep:
        try:
            config_dict = config.model_dump()
            
            # Check if API keys are in config file (they should be in .env instead)
            api_key_fields = ["api_key", "apiKey", "bot_token", "botToken"]
            found_keys = []
            
            def check_dict(d, path=""):
                for key, value in d.items():
                    if key in api_key_fields and value:
                        found_keys.append(f"{path}.{key}" if path else key)
                    if isinstance(value, dict):
                        check_dict(value, f"{path}.{key}" if path else key)
            
            check_dict(config_dict)
            
            if found_keys:
                results["warnings"].append({
                    "check": "api_keys_in_config",
                    "message": f"API keys found in config file: {', '.join(found_keys)}",
                    "fix": "Move API keys to .env file for better security",
                })
                console.print("[yellow]⚠[/yellow]  API keys found in config file")
                console.print("    Recommendation: Move to .env file")
        except Exception:
            pass
    
    # Summary
    console.print()
    if json_output:
        import json
        print(json.dumps(results, indent=2))
    else:
        if results["critical"]:
            console.print(f"[red]✗[/red] {len(results['critical'])} critical issue(s):")
            for item in results["critical"]:
                console.print(f"  - {item['message']}")
                if "fix" in item:
                    console.print(f"    Fix: {item['fix']}")
        
        if results["warnings"]:
            console.print(f"[yellow]⚠[/yellow]  {len(results['warnings'])} warning(s):")
            for item in results["warnings"]:
                console.print(f"  - {item['message']}")
                if "fix" in item:
                    console.print(f"    Fix: {item['fix']}")
        
        if results["info"]:
            console.print(f"[cyan]ℹ[/cyan]  {len(results['info'])} info:")
            for item in results["info"]:
                console.print(f"  - {item['message']}")
                if "info" in item:
                    console.print(f"    {item['info']}")
        
        if not results["critical"] and not results["warnings"]:
            console.print("[green]✓[/green] No security issues found!")
        
        if fix:
            console.print("\n[cyan]Applied automatic fixes where possible[/cyan]")
    
    if results["critical"] and not json_output:
        raise typer.Exit(1)
