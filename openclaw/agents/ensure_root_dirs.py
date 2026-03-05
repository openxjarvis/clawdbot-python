"""Root directory initialization for OpenClaw.

Ensures all necessary root-level directories and files exist, matching
TypeScript openclaw directory structure:
- identity/ - Device identity files
- delivery-queue/ - Message queue
- completions/ - Shell completion scripts
- canvas/ - Interactive canvas with index.html
- logs/ - Log files including gateway.err.log
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def ensure_identity_dir(root_dir: Path) -> dict:
    """Ensure identity/ directory and device identity files exist.
    
    Creates:
    - identity/device.json - Device identifier
    - identity/device-auth.json - Device authentication data
    
    Args:
        root_dir: OpenClaw root directory
        
    Returns:
        Dict with device info
    """
    identity_dir = root_dir / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    
    device_file = identity_dir / "device.json"
    device_auth_file = identity_dir / "device-auth.json"
    
    result = {"dir": identity_dir}
    
    # Create device.json if missing
    if not device_file.exists():
        device_id = f"device_{secrets.token_hex(8)}"
        device_data = {
            "deviceId": device_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "platform": "python",
            "version": "1.0.0"
        }
        device_file.write_text(json.dumps(device_data, indent=2) + "\n", encoding="utf-8")
        logger.info("Created device identity: %s", device_file)
        result["device_id"] = device_id
    else:
        try:
            device_data = json.loads(device_file.read_text(encoding="utf-8"))
            result["device_id"] = device_data.get("deviceId")
        except Exception as e:
            logger.warning("Failed to read device.json: %s", e)
    
    # Create device-auth.json if missing (empty initially)
    if not device_auth_file.exists():
        auth_data = {
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "tokens": {}
        }
        device_auth_file.write_text(json.dumps(auth_data, indent=2) + "\n", encoding="utf-8")
        logger.info("Created device auth: %s", device_auth_file)
    
    return result


def ensure_delivery_queue_dir(root_dir: Path) -> dict:
    """Ensure delivery-queue/ directory exists for message queuing.
    
    Args:
        root_dir: OpenClaw root directory
        
    Returns:
        Dict with directory info
    """
    queue_dir = root_dir / "delivery-queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    
    # Create .gitignore to exclude queue files from git
    gitignore = queue_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*.json\n!.gitignore\n", encoding="utf-8")
    
    logger.debug("Delivery queue directory: %s", queue_dir)
    return {"dir": queue_dir}


def ensure_completions_dir(root_dir: Path) -> dict:
    """Ensure completions/ directory exists with shell completion scripts.
    
    Creates placeholder completion scripts for:
    - bash
    - zsh
    - fish
    - powershell
    
    Args:
        root_dir: OpenClaw root directory
        
    Returns:
        Dict with directory info
    """
    completions_dir = root_dir / "completions"
    completions_dir.mkdir(parents=True, exist_ok=True)
    
    # Create placeholder completion scripts
    completions = {
        "openclaw.bash": _bash_completion_template(),
        "openclaw.zsh": _zsh_completion_template(),
        "openclaw.fish": _fish_completion_template(),
        "openclaw.ps1": _powershell_completion_template(),
    }
    
    for filename, content in completions.items():
        completion_file = completions_dir / filename
        if not completion_file.exists():
            completion_file.write_text(content, encoding="utf-8")
            logger.info("Created completion script: %s", filename)
    
    return {"dir": completions_dir}


def ensure_canvas_dir(root_dir: Path) -> dict:
    """Ensure canvas/ directory exists with index.html.
    
    Creates interactive canvas page matching TypeScript version.
    
    Args:
        root_dir: OpenClaw root directory
        
    Returns:
        Dict with directory info
    """
    canvas_dir = root_dir / "canvas"
    canvas_dir.mkdir(parents=True, exist_ok=True)
    
    index_file = canvas_dir / "index.html"
    if not index_file.exists():
        index_file.write_text(_canvas_html_template(), encoding="utf-8")
        logger.info("Created canvas index.html: %s", index_file)
    
    return {"dir": canvas_dir, "index_file": index_file}


def ensure_logs_dir(root_dir: Path) -> dict:
    """Ensure logs/ directory exists with necessary log files.
    
    Creates:
    - gateway.log - Main gateway log
    - gateway.err.log - Gateway error log
    - config-audit.jsonl - Config audit log
    
    Args:
        root_dir: OpenClaw root directory
        
    Returns:
        Dict with directory info
    """
    logs_dir = root_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Create log files if missing (empty files)
    log_files = ["gateway.log", "gateway.err.log"]
    for log_file in log_files:
        log_path = logs_dir / log_file
        if not log_path.exists():
            log_path.touch()
            logger.info("Created log file: %s", log_file)
    
    # Create config-audit.jsonl if missing
    audit_log = logs_dir / "config-audit.jsonl"
    if not audit_log.exists():
        audit_log.touch()
        logger.info("Created config audit log: %s", audit_log)
    
    return {"dir": logs_dir}


def ensure_media_dir(root_dir: Path) -> dict:
    """Ensure media/ directory exists for media pipeline storage.

    Mirrors TS src/media/store.ts — resolveMediaDir() = stateDir/media.
    Creates media/ and media/remote-cache/ (used by the media server for
    remote-URL downloads keyed by session).

    Args:
        root_dir: OpenClaw root directory

    Returns:
        Dict with directory info
    """
    media_dir = root_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / "remote-cache").mkdir(exist_ok=True)
    logger.debug("Media directory: %s", media_dir)
    return {"dir": str(media_dir)}


def ensure_sandboxes_dir(root_dir: Path) -> dict:
    """Ensure sandboxes/ directory exists for per-session sandbox workspaces.

    Mirrors TS src/agents/sandbox/constants.ts — DEFAULT_SANDBOX_WORKSPACE_ROOT =
    stateDir/sandboxes. Each sandbox session mounts its own subdirectory here.

    Args:
        root_dir: OpenClaw root directory

    Returns:
        Dict with directory info
    """
    sandboxes_dir = root_dir / "sandboxes"
    sandboxes_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Sandboxes directory: %s", sandboxes_dir)
    return {"dir": str(sandboxes_dir)}


def ensure_root_directories(root_dir: str | Path) -> dict:
    """Ensure all necessary root-level directories and files exist.
    
    Creates:
    - identity/ - Device identity files
    - delivery-queue/ - Message queue
    - completions/ - Shell completion scripts
    - canvas/ - Interactive canvas with index.html
    - logs/ - Log files including gateway.err.log
    - media/ - Media pipeline storage (+ media/remote-cache/)
    - sandboxes/ - Per-session Docker sandbox workspace roots
    
    Args:
        root_dir: OpenClaw root directory path
        
    Returns:
        Dict with status of each directory
    """
    if isinstance(root_dir, str):
        root_dir = Path(root_dir).expanduser().resolve()
    
    root_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Root directory: %s", root_dir)
    
    result = {"root_dir": root_dir}
    
    # Ensure each directory
    try:
        result["identity"] = ensure_identity_dir(root_dir)
    except Exception as e:
        logger.warning("Failed to ensure identity dir: %s", e)
        result["identity"] = {"error": str(e)}
    
    try:
        result["delivery_queue"] = ensure_delivery_queue_dir(root_dir)
    except Exception as e:
        logger.warning("Failed to ensure delivery-queue dir: %s", e)
        result["delivery_queue"] = {"error": str(e)}
    
    try:
        result["completions"] = ensure_completions_dir(root_dir)
    except Exception as e:
        logger.warning("Failed to ensure completions dir: %s", e)
        result["completions"] = {"error": str(e)}
    
    try:
        result["canvas"] = ensure_canvas_dir(root_dir)
    except Exception as e:
        logger.warning("Failed to ensure canvas dir: %s", e)
        result["canvas"] = {"error": str(e)}
    
    try:
        result["logs"] = ensure_logs_dir(root_dir)
    except Exception as e:
        logger.warning("Failed to ensure logs dir: %s", e)
        result["logs"] = {"error": str(e)}

    try:
        result["media"] = ensure_media_dir(root_dir)
    except Exception as e:
        logger.warning("Failed to ensure media dir: %s", e)
        result["media"] = {"error": str(e)}

    try:
        result["sandboxes"] = ensure_sandboxes_dir(root_dir)
    except Exception as e:
        logger.warning("Failed to ensure sandboxes dir: %s", e)
        result["sandboxes"] = {"error": str(e)}

    return result


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def _bash_completion_template() -> str:
    """Return bash completion script template."""
    return """# OpenClaw bash completion script
# Generated by openclaw-python

_openclaw_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="start stop restart status config agent gateway tui chat daemon"
    
    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "--help --version --config --workspace --verbose --quiet" -- ${cur}) )
        return 0
    fi
    
    COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    return 0
}

complete -F _openclaw_completion openclaw
"""


def _zsh_completion_template() -> str:
    """Return zsh completion script template."""
    return """#compdef openclaw
# OpenClaw zsh completion script
# Generated by openclaw-python

_openclaw() {
    local -a commands
    commands=(
        'start:Start OpenClaw services'
        'stop:Stop OpenClaw services'
        'restart:Restart OpenClaw services'
        'status:Show service status'
        'config:Manage configuration'
        'agent:Run agent commands'
        'gateway:Gateway operations'
        'tui:Launch terminal UI'
        'chat:Interactive chat'
        'daemon:Daemon management'
    )
    
    _arguments -C \
        '1: :->command' \
        '*::arg:->args' \
        '--help[Show help]' \
        '--version[Show version]' \
        '--config[Config file path]' \
        '--workspace[Workspace directory]' \
        '--verbose[Verbose output]' \
        '--quiet[Quiet mode]'
    
    case $state in
        command)
            _describe 'command' commands
            ;;
    esac
}

_openclaw "$@"
"""


def _fish_completion_template() -> str:
    """Return fish completion script template."""
    return """# OpenClaw fish completion script
# Generated by openclaw-python

complete -c openclaw -f

# Commands
complete -c openclaw -n "__fish_use_subcommand" -a start -d "Start OpenClaw services"
complete -c openclaw -n "__fish_use_subcommand" -a stop -d "Stop OpenClaw services"
complete -c openclaw -n "__fish_use_subcommand" -a restart -d "Restart OpenClaw services"
complete -c openclaw -n "__fish_use_subcommand" -a status -d "Show service status"
complete -c openclaw -n "__fish_use_subcommand" -a config -d "Manage configuration"
complete -c openclaw -n "__fish_use_subcommand" -a agent -d "Run agent commands"
complete -c openclaw -n "__fish_use_subcommand" -a gateway -d "Gateway operations"
complete -c openclaw -n "__fish_use_subcommand" -a tui -d "Launch terminal UI"
complete -c openclaw -n "__fish_use_subcommand" -a chat -d "Interactive chat"
complete -c openclaw -n "__fish_use_subcommand" -a daemon -d "Daemon management"

# Global options
complete -c openclaw -l help -d "Show help"
complete -c openclaw -l version -d "Show version"
complete -c openclaw -l config -d "Config file path"
complete -c openclaw -l workspace -d "Workspace directory"
complete -c openclaw -l verbose -d "Verbose output"
complete -c openclaw -l quiet -d "Quiet mode"
"""


def _powershell_completion_template() -> str:
    """Return PowerShell completion script template."""
    return """# OpenClaw PowerShell completion script
# Generated by openclaw-python

Register-ArgumentCompleter -Native -CommandName openclaw -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    
    $commands = @(
        'start',
        'stop',
        'restart',
        'status',
        'config',
        'agent',
        'gateway',
        'tui',
        'chat',
        'daemon'
    )
    
    $options = @(
        '--help',
        '--version',
        '--config',
        '--workspace',
        '--verbose',
        '--quiet'
    )
    
    $completions = $commands + $options
    
    $completions | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}
"""


def _canvas_html_template() -> str:
    """Return canvas index.html template (matching TypeScript version)."""
    return """<!doctype html>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>OpenClaw Canvas</title>
<style>
  html, body { height: 100%; margin: 0; background: #000; color: #fff; font: 16px/1.4 -apple-system, BlinkMacSystemFont, system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
  .wrap { min-height: 100%; display: grid; place-items: center; padding: 24px; }
  .card { width: min(720px, 100%); background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.10); border-radius: 16px; padding: 18px 18px 14px; }
  .title { display: flex; align-items: baseline; gap: 10px; }
  h1 { margin: 0; font-size: 22px; letter-spacing: 0.2px; }
  .sub { opacity: 0.75; font-size: 13px; }
  .row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
  button { appearance: none; border: 1px solid rgba(255,255,255,0.14); background: rgba(255,255,255,0.10); color: #fff; padding: 10px 12px; border-radius: 12px; font-weight: 600; cursor: pointer; }
  button:active { transform: translateY(1px); }
  .ok { color: #24e08a; }
  .bad { color: #ff5c5c; }
  .log { margin-top: 14px; opacity: 0.85; font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; white-space: pre-wrap; background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.08); padding: 10px; border-radius: 12px; }
</style>
<div class="wrap">
  <div class="card">
    <div class="title">
      <h1>OpenClaw Canvas</h1>
      <div class="sub">Interactive test page (auto-reload enabled)</div>
    </div>

    <div class="row">
      <button id="btn-hello">Hello</button>
      <button id="btn-time">Time</button>
      <button id="btn-photo">Photo</button>
      <button id="btn-dalek">Dalek</button>
    </div>

    <div id="status" class="sub" style="margin-top: 10px;"></div>
    <div id="log" class="log">Ready.</div>
  </div>
</div>
<script>
(() => {
  const logEl = document.getElementById("log");
  const statusEl = document.getElementById("status");
  const log = (msg) => { logEl.textContent = String(msg); };

  const hasIOS = () =>
    !!(
      window.webkit &&
      window.webkit.messageHandlers &&
      window.webkit.messageHandlers.openclawCanvasA2UIAction
    );
  const hasAndroid = () =>
    !!(
      (window.openclawCanvasA2UIAction &&
        typeof window.openclawCanvasA2UIAction.postMessage === "function")
    );
  const hasHelper = () => typeof window.openclawSendUserAction === "function";
  statusEl.innerHTML =
    "Bridge: " +
    (hasHelper() ? "<span class='ok'>ready</span>" : "<span class='bad'>missing</span>") +
    " · iOS=" + (hasIOS() ? "yes" : "no") +
    " · Android=" + (hasAndroid() ? "yes" : "no");

  const onStatus = (ev) => {
    const d = ev && ev.detail || {};
    log("Action status: id=" + (d.id || "?") + " ok=" + String(!!d.ok) + (d.error ? (" error=" + d.error) : ""));
  };
  window.addEventListener("openclaw:a2ui-action-status", onStatus);

  function send(name, sourceComponentId) {
    if (!hasHelper()) {
      log("No action bridge found. Ensure you're viewing this on an iOS/Android OpenClaw node canvas.");
      return;
    }
    const sendUserAction =
      typeof window.openclawSendUserAction === "function"
        ? window.openclawSendUserAction
        : undefined;
    const ok = sendUserAction({
      name,
      surfaceId: "main",
      sourceComponentId,
      context: { t: Date.now() },
    });
    log(ok ? ("Sent action: " + name) : ("Failed to send action: " + name));
  }

  document.getElementById("btn-hello").onclick = () => send("hello", "demo.hello");
  document.getElementById("btn-time").onclick = () => send("time", "demo.time");
  document.getElementById("btn-photo").onclick = () => send("photo", "demo.photo");
  document.getElementById("btn-dalek").onclick = () => send("dalek", "demo.dalek");
})();
</script>
"""


__all__ = [
    "ensure_root_directories",
    "ensure_identity_dir",
    "ensure_delivery_queue_dir",
    "ensure_completions_dir",
    "ensure_canvas_dir",
    "ensure_logs_dir",
    "ensure_media_dir",
    "ensure_sandboxes_dir",
]
