---
summary: "How OpenClaw sandboxing works: modes, scopes, workspace access, and images"
title: Sandboxing
read_when: "You want a dedicated explanation of sandboxing or need to tune agents.defaults.sandbox."
status: active
---

# Sandboxing

OpenClaw can run **tools inside Docker containers** to reduce blast radius.
This is **optional** and controlled by configuration (`agents.defaults.sandbox` or
`agents.list[].sandbox`). If sandboxing is off, tools run on the host.
The Gateway stays on the host; tool execution runs in an isolated sandbox
when enabled.

This is not a perfect security boundary, but it materially limits filesystem
and process access when the model does something dumb.

## What gets sandboxed

- Tool execution (`exec`, `read`, `write`, `edit`, `apply_patch`, `process`, etc.).
- Optional sandboxed browser (`agents.defaults.sandbox.browser`).

Not sandboxed:

- The Gateway process itself.
- Any tool explicitly allowed to run on the host (e.g. `tools.elevated`).
  - **Elevated exec runs on the host and bypasses sandboxing.**

## Modes

`agents.defaults.sandbox.mode` controls **when** sandboxing is used:

- `"off"`: no sandboxing.
- `"non-main"`: sandbox only **non-main** sessions (default if you want normal chats on host).
- `"all"`: every session runs in a sandbox.

## Scope

`agents.defaults.sandbox.scope` controls **how many containers** are created:

- `"session"` (default): one container per session.
- `"agent"`: one container per agent.
- `"shared"`: one container shared by all sandboxed sessions.

## Workspace access

`agents.defaults.sandbox.workspaceAccess` controls **what the sandbox can see**:

- `"none"` (default): tools see a sandbox workspace under `~/.openclaw/sandboxes`.
- `"ro"`: mounts the agent workspace read-only at `/agent` (disables `write`/`edit`/`apply_patch`).
- `"rw"`: mounts the agent workspace read/write at `/workspace`.

## Custom bind mounts

`agents.defaults.sandbox.docker.binds` mounts additional host directories into the container.
Format: `host:container:mode` (e.g., `"/home/user/source:/source:rw"`).

Global and per-agent binds are **merged** (not replaced).

Example (read-only source + an extra data directory):

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "docker": {
          "binds": ["/home/user/source:/source:ro", "/var/data/myapp:/data:ro"]
        }
      }
    },
    "list": [
      {
        "id": "build",
        "sandbox": {
          "docker": {
            "binds": ["/mnt/cache:/cache:rw"]
          }
        }
      }
    ]
  }
}
```

Security notes:

- Binds bypass the sandbox filesystem: they expose host paths with whatever mode you set (`:ro` or `:rw`).
- OpenClaw blocks dangerous bind sources (for example: `docker.sock`, `/etc`, `/proc`, `/sys`, `/dev`).
- Sensitive mounts (secrets, SSH keys) should be `:ro` unless absolutely required.

## Images + setup

Default image: `openclaw-sandbox:bookworm-slim`

Build it once:

```bash
scripts/sandbox-setup.sh
```

Note: the default image does **not** include Python or Node. If a skill needs them,
either bake a custom image or install via `sandbox.docker.setupCommand` (requires network egress + writable root + root user).

By default, sandbox containers run with **no network**.
Override with `agents.defaults.sandbox.docker.network`.

## setupCommand (one-time container setup)

`setupCommand` runs **once** after the sandbox container is created (not on every run).
It executes inside the container via `sh -lc`.

Common pitfalls:

- Default `docker.network` is `"none"` (no egress), so package installs will fail.
- `readOnlyRoot: true` prevents writes; set `readOnlyRoot: false` or bake a custom image.
- `user` must be root for package installs (omit `user` or set `user: "0:0"`).
- Sandbox exec does **not** inherit host process env. Use
  `agents.defaults.sandbox.docker.env` (or a custom image) for skill API keys.

## Tool policy + escape hatches

Tool allow/deny policies still apply before sandbox rules. If a tool is denied
globally or per-agent, sandboxing doesn't bring it back.

`tools.elevated` is an explicit escape hatch that runs `exec` on the host.

Debugging:

- Use `openclaw sandbox explain` to inspect effective sandbox mode, tool policy, and fix-it config keys.
- See [Sandbox vs Tool Policy vs Elevated](/gateway/sandbox-vs-tool-policy-vs-elevated) for the "why is this blocked?" mental model.

## Minimal enable example

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "non-main",
        "scope": "session",
        "workspaceAccess": "none"
      }
    }
  }
}
```

## Related docs

- [Sandbox Configuration](/gateway/configuration#agentsdefaults-sandbox)
- [Security](/gateway/security)
