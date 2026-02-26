"""Ensure shell completion scripts exist in ~/.openclaw/completions/

TS alignment: openclaw/src/completions/ scripts are copied to ~/.openclaw/completions/
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..config.paths import resolve_state_dir

logger = logging.getLogger(__name__)

COMPLETION_SCRIPTS = ["openclaw.bash", "openclaw.zsh", "openclaw.fish", "openclaw.ps1"]


def ensure_completion_scripts() -> dict[str, bool]:
    """Ensure shell completion scripts exist in ~/.openclaw/completions/
    
    Creates the completions directory and generates basic completion scripts
    if they don't exist. This matches TS behavior where completion scripts
    are available in the .openclaw directory.
    
    Returns:
        Dict mapping script names to whether they were created
    """
    results = {}
    
    try:
        completions_dir = resolve_state_dir() / "completions"
        completions_dir.mkdir(parents=True, exist_ok=True)
        
        for script_name in COMPLETION_SCRIPTS:
            target_path = completions_dir / script_name
            
            if target_path.exists():
                results[script_name] = False
                continue
            
            # Generate basic completion script
            content = _generate_completion_script(script_name)
            if content:
                target_path.write_text(content, encoding="utf-8")
                target_path.chmod(0o755)
                results[script_name] = True
                logger.debug(f"Created completion script: {script_name}")
            else:
                results[script_name] = False
        
        logger.info(f"Completion scripts ensured in {completions_dir}")
        
    except Exception as e:
        logger.error(f"Failed to ensure completion scripts: {e}", exc_info=True)
        for script_name in COMPLETION_SCRIPTS:
            results[script_name] = False
    
    return results


def _generate_completion_script(script_name: str) -> str | None:
    """Generate basic completion script content
    
    Args:
        script_name: Name of the script (e.g., "openclaw.bash")
        
    Returns:
        Script content or None if unsupported
    """
    if script_name == "openclaw.bash":
        return _BASH_COMPLETION
    elif script_name == "openclaw.zsh":
        return _ZSH_COMPLETION
    elif script_name == "openclaw.fish":
        return _FISH_COMPLETION
    elif script_name == "openclaw.ps1":
        return _POWERSHELL_COMPLETION
    return None


# Basic completion scripts (simplified versions)
# These provide basic command completion for the most common commands

_BASH_COMPLETION = """
_openclaw_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Top-level commands
    opts="setup onboard configure config doctor dashboard reset uninstall message memory agent agents status health sessions browser completion acp gateway daemon logs system models approvals nodes devices node sandbox tui cron dns docs hooks webhooks pairing plugins channels directory security skills update --version --help"
    
    case "${prev}" in
        onboard)
            opts="--workspace --reset --non-interactive --accept-risk --flow --mode --skip-ui --skip-health"
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            return 0
            ;;
        gateway)
            opts="run start stop status health --port --bind --auth --token"
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            return 0
            ;;
        agent)
            opts="--message -m --session-id --agent --thinking --verbose"
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            return 0
            ;;
        *)
            ;;
    esac
    
    COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    return 0
}

complete -F _openclaw_completion openclaw
"""

_ZSH_COMPLETION = """
#compdef openclaw

_openclaw() {
    local -a commands
    commands=(
        'setup:Initialize ~/.openclaw/openclaw.json and workspace'
        'onboard:Interactive wizard for setup'
        'configure:Interactive credential configuration'
        'config:Config helpers (get/set/unset)'
        'doctor:Health checks and quick fixes'
        'dashboard:Open Control UI'
        'reset:Reset local config/state'
        'uninstall:Uninstall gateway service'
        'message:Send messages and channel actions'
        'memory:Memory search tools'
        'agent:Run an agent turn'
        'agents:Manage isolated agents'
        'status:Show channel health'
        'health:Fetch health from gateway'
        'sessions:List conversation sessions'
        'browser:Manage browser'
        'completion:Generate shell completion'
        'acp:Run ACP bridge'
        'gateway:Run WebSocket Gateway'
        'daemon:Manage Gateway service'
        'logs:Tail gateway logs'
        'system:System tools'
        'models:Model configuration'
        'approvals:Manage exec approvals'
        'nodes:Manage node pairing'
        'devices:Device pairing'
        'node:Run headless node host'
        'sandbox:Manage sandbox containers'
        'tui:Open terminal UI'
        'cron:Manage cron jobs'
        'dns:DNS helpers'
        'docs:Search docs'
        'hooks:Manage hooks'
        'webhooks:Webhook helpers'
        'pairing:Secure DM pairing'
        'plugins:Manage plugins'
        'channels:Manage chat channels'
        'directory:Directory lookups'
        'security:Security tools'
        'skills:List skills'
        'update:Update OpenClaw'
    )
    
    _arguments -C \
        '(--version -V)'{--version,-V}'[Show version]' \
        '--help[Show help]' \
        "1: :->cmds" \
        "*::arg:->args"
    
    case $state in
        cmds)
            _describe 'command' commands
            ;;
        args)
            case $line[1] in
                onboard)
                    _arguments \
                        '--workspace[Workspace directory]' \
                        '--reset[Reset before running]' \
                        '--non-interactive[No prompts]' \
                        '--accept-risk[Accept risk acknowledgement]' \
                        '--flow[Wizard flow]:flow:(quickstart advanced manual)' \
                        '--mode[Mode]:mode:(local remote)' \
                        '--skip-ui[Skip UI launch]' \
                        '--skip-health[Skip health check]'
                    ;;
                gateway)
                    _arguments \
                        '1: :->gateway_cmds' \
                        '--port[Gateway port]' \
                        '--bind[Bind address]' \
                        '--auth[Auth mode]' \
                        '--token[Auth token]'
                    
                    case $state in
                        gateway_cmds)
                            _values 'gateway command' 'run' 'start' 'stop' 'status' 'health'
                            ;;
                    esac
                    ;;
                agent)
                    _arguments \
                        '(--message -m)'{--message,-m}'[Message to send]' \
                        '--session-id[Session ID]' \
                        '--agent[Agent name]' \
                        '--thinking[Show thinking]' \
                        '--verbose[Verbose output]'
                    ;;
            esac
            ;;
    esac
}

_openclaw "$@"
"""

_FISH_COMPLETION = """
# openclaw completion for fish

# Main commands
complete -c openclaw -f -n __fish_use_subcommand -a setup -d 'Initialize configuration'
complete -c openclaw -f -n __fish_use_subcommand -a onboard -d 'Interactive wizard'
complete -c openclaw -f -n __fish_use_subcommand -a configure -d 'Configure credentials'
complete -c openclaw -f -n __fish_use_subcommand -a config -d 'Config helpers'
complete -c openclaw -f -n __fish_use_subcommand -a doctor -d 'Health checks'
complete -c openclaw -f -n __fish_use_subcommand -a dashboard -d 'Open Control UI'
complete -c openclaw -f -n __fish_use_subcommand -a reset -d 'Reset config'
complete -c openclaw -f -n __fish_use_subcommand -a uninstall -d 'Uninstall service'
complete -c openclaw -f -n __fish_use_subcommand -a message -d 'Send messages'
complete -c openclaw -f -n __fish_use_subcommand -a memory -d 'Memory tools'
complete -c openclaw -f -n __fish_use_subcommand -a agent -d 'Run agent'
complete -c openclaw -f -n __fish_use_subcommand -a agents -d 'Manage agents'
complete -c openclaw -f -n __fish_use_subcommand -a status -d 'Show status'
complete -c openclaw -f -n __fish_use_subcommand -a health -d 'Check health'
complete -c openclaw -f -n __fish_use_subcommand -a sessions -d 'List sessions'
complete -c openclaw -f -n __fish_use_subcommand -a browser -d 'Manage browser'
complete -c openclaw -f -n __fish_use_subcommand -a completion -d 'Shell completion'
complete -c openclaw -f -n __fish_use_subcommand -a acp -d 'ACP bridge'
complete -c openclaw -f -n __fish_use_subcommand -a gateway -d 'Gateway service'
complete -c openclaw -f -n __fish_use_subcommand -a daemon -d 'Daemon service'
complete -c openclaw -f -n __fish_use_subcommand -a logs -d 'View logs'
complete -c openclaw -f -n __fish_use_subcommand -a system -d 'System tools'
complete -c openclaw -f -n __fish_use_subcommand -a models -d 'Model config'
complete -c openclaw -f -n __fish_use_subcommand -a approvals -d 'Exec approvals'
complete -c openclaw -f -n __fish_use_subcommand -a nodes -d 'Node pairing'
complete -c openclaw -f -n __fish_use_subcommand -a devices -d 'Device pairing'
complete -c openclaw -f -n __fish_use_subcommand -a node -d 'Node host'
complete -c openclaw -f -n __fish_use_subcommand -a sandbox -d 'Sandbox containers'
complete -c openclaw -f -n __fish_use_subcommand -a tui -d 'Terminal UI'
complete -c openclaw -f -n __fish_use_subcommand -a cron -d 'Cron jobs'
complete -c openclaw -f -n __fish_use_subcommand -a dns -d 'DNS helpers'
complete -c openclaw -f -n __fish_use_subcommand -a docs -d 'Search docs'
complete -c openclaw -f -n __fish_use_subcommand -a hooks -d 'Manage hooks'
complete -c openclaw -f -n __fish_use_subcommand -a webhooks -d 'Webhooks'
complete -c openclaw -f -n __fish_use_subcommand -a pairing -d 'DM pairing'
complete -c openclaw -f -n __fish_use_subcommand -a plugins -d 'Plugins'
complete -c openclaw -f -n __fish_use_subcommand -a channels -d 'Chat channels'
complete -c openclaw -f -n __fish_use_subcommand -a directory -d 'Directory'
complete -c openclaw -f -n __fish_use_subcommand -a security -d 'Security'
complete -c openclaw -f -n __fish_use_subcommand -a skills -d 'Skills'
complete -c openclaw -f -n __fish_use_subcommand -a update -d 'Update OpenClaw'

# Global options
complete -c openclaw -l version -s V -d 'Show version'
complete -c openclaw -l help -d 'Show help'

# onboard command
complete -c openclaw -n '__fish_seen_subcommand_from onboard' -l workspace -d 'Workspace directory'
complete -c openclaw -n '__fish_seen_subcommand_from onboard' -l reset -d 'Reset before running'
complete -c openclaw -n '__fish_seen_subcommand_from onboard' -l non-interactive -d 'No prompts'
complete -c openclaw -n '__fish_seen_subcommand_from onboard' -l accept-risk -d 'Accept risk'
complete -c openclaw -n '__fish_seen_subcommand_from onboard' -l flow -d 'Wizard flow' -a 'quickstart advanced manual'
complete -c openclaw -n '__fish_seen_subcommand_from onboard' -l mode -d 'Mode' -a 'local remote'
complete -c openclaw -n '__fish_seen_subcommand_from onboard' -l skip-ui -d 'Skip UI launch'
complete -c openclaw -n '__fish_seen_subcommand_from onboard' -l skip-health -d 'Skip health check'

# gateway command
complete -c openclaw -n '__fish_seen_subcommand_from gateway' -f -a 'run start stop status health'
complete -c openclaw -n '__fish_seen_subcommand_from gateway' -l port -d 'Gateway port'
complete -c openclaw -n '__fish_seen_subcommand_from gateway' -l bind -d 'Bind address'
complete -c openclaw -n '__fish_seen_subcommand_from gateway' -l auth -d 'Auth mode'
complete -c openclaw -n '__fish_seen_subcommand_from gateway' -l token -d 'Auth token'

# agent command
complete -c openclaw -n '__fish_seen_subcommand_from agent' -l message -s m -d 'Message to send'
complete -c openclaw -n '__fish_seen_subcommand_from agent' -l session-id -d 'Session ID'
complete -c openclaw -n '__fish_seen_subcommand_from agent' -l agent -d 'Agent name'
complete -c openclaw -n '__fish_seen_subcommand_from agent' -l thinking -d 'Show thinking'
complete -c openclaw -n '__fish_seen_subcommand_from agent' -l verbose -d 'Verbose output'
"""

_POWERSHELL_COMPLETION = """
# PowerShell completion for openclaw

Register-ArgumentCompleter -Native -CommandName openclaw -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    
    $commands = @(
        @{Name='setup'; Description='Initialize configuration'},
        @{Name='onboard'; Description='Interactive wizard'},
        @{Name='configure'; Description='Configure credentials'},
        @{Name='config'; Description='Config helpers'},
        @{Name='doctor'; Description='Health checks'},
        @{Name='dashboard'; Description='Open Control UI'},
        @{Name='reset'; Description='Reset config'},
        @{Name='uninstall'; Description='Uninstall service'},
        @{Name='message'; Description='Send messages'},
        @{Name='memory'; Description='Memory tools'},
        @{Name='agent'; Description='Run agent'},
        @{Name='agents'; Description='Manage agents'},
        @{Name='status'; Description='Show status'},
        @{Name='health'; Description='Check health'},
        @{Name='sessions'; Description='List sessions'},
        @{Name='browser'; Description='Manage browser'},
        @{Name='completion'; Description='Shell completion'},
        @{Name='acp'; Description='ACP bridge'},
        @{Name='gateway'; Description='Gateway service'},
        @{Name='daemon'; Description='Daemon service'},
        @{Name='logs'; Description='View logs'},
        @{Name='system'; Description='System tools'},
        @{Name='models'; Description='Model config'},
        @{Name='approvals'; Description='Exec approvals'},
        @{Name='nodes'; Description='Node pairing'},
        @{Name='devices'; Description='Device pairing'},
        @{Name='node'; Description='Node host'},
        @{Name='sandbox'; Description='Sandbox containers'},
        @{Name='tui'; Description='Terminal UI'},
        @{Name='cron'; Description='Cron jobs'},
        @{Name='dns'; Description='DNS helpers'},
        @{Name='docs'; Description='Search docs'},
        @{Name='hooks'; Description='Manage hooks'},
        @{Name='webhooks'; Description='Webhooks'},
        @{Name='pairing'; Description='DM pairing'},
        @{Name='plugins'; Description='Plugins'},
        @{Name='channels'; Description='Chat channels'},
        @{Name='directory'; Description='Directory'},
        @{Name='security'; Description='Security'},
        @{Name='skills'; Description='Skills'},
        @{Name='update'; Description='Update OpenClaw'}
    )
    
    $commands | Where-Object {
        $_.Name -like "$wordToComplete*"
    } | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new(
            $_.Name,
            $_.Name,
            'ParameterValue',
            $_.Description
        )
    }
}
"""


__all__ = ["ensure_completion_scripts"]
