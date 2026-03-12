---
summary: "Agent bootstrapping ritual that seeds the workspace and identity files"
read_when:
  - Understanding what happens on the first agent run
  - Explaining where bootstrapping files live
  - Debugging onboarding identity setup
title: "Agent Bootstrapping"
sidebarTitle: "Bootstrapping"
---

# Agent Bootstrapping

Bootstrapping is the **first-run** ritual that prepares an agent workspace and
collects identity details. It happens after onboarding, when the agent starts
for the first time.

## What bootstrapping does

On the first agent run, OpenClaw Python bootstraps the workspace (default
`~/.openclaw/workspace`):

- Seeds `AGENTS.md`, `BOOTSTRAP.md`, `IDENTITY.md`, `USER.md`.
- Runs a short Q&A ritual (one question at a time).
- Writes identity + preferences to `IDENTITY.md`, `USER.md`, `SOUL.md`.
- Removes `BOOTSTRAP.md` when finished so it only runs once.

## Where it runs

Bootstrapping always runs on the **gateway host**. If you connect to a
remote Gateway, the workspace and bootstrapping files live on that remote
machine.

> When the Gateway runs on another machine, edit workspace files on the gateway
> host (for example, `user@gateway-host:~/.openclaw/workspace`).

## Related docs

- Onboarding: [Getting Started](/start/getting-started)
- Workspace layout: [Agent workspace](/concepts/agent-workspace)
