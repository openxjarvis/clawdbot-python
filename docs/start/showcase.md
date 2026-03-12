---
title: "Showcase"
description: "Real-world OpenClaw projects from the community"
summary: "Community-built projects and integrations powered by OpenClaw"
---

# Showcase

Real projects from the community. See what people are building with OpenClaw.

> **Want to be featured?** Share your project in [#showcase on Discord](https://discord.gg/clawd) or [tag @openclaw on X](https://x.com/openclaw).

## OpenClaw in Action

Full setup walkthrough (28m) by VelvetShark: [Watch on YouTube](https://www.youtube.com/watch?v=SaWSPZoPX34)

## Fresh from Discord

### PR Review to Telegram Feedback

**@bangnokia** — `review` `github` `telegram`

OpenCode finishes the change, opens a PR, OpenClaw reviews the diff and replies in Telegram with "minor suggestions" plus a clear merge verdict (including critical fixes to apply first).

### Wine Cellar Skill in Minutes

**@prades_maxime** — `skills` `local` `csv`

Asked "Robby" for a local wine cellar skill. It requests a sample CSV export + where to store it, then builds/tests the skill fast (962 bottles in the example).

### Tesco Shop Autopilot

**@marchattonhere** — `automation` `browser` `shopping`

Weekly meal plan → regulars → book delivery slot → confirm order. No APIs, just browser control.

### SNAG Screenshot-to-Markdown

**@am-will** — `devtools` `screenshots` `markdown`

[GitHub](https://github.com/am-will/snag) — Hotkey a screen region → Gemini vision → instant Markdown in your clipboard.

### Agents UI

**@kitze** — `ui` `skills` `sync`

[releaseflow.net](https://releaseflow.net/kitze/agents-ui) — Desktop app to manage skills/commands across Agents, Claude, Codex, and OpenClaw.

### CodexMonitor

**@odrobnik** — `devtools` `codex` `brew`

[ClawHub](https://clawhub.com/odrobnik/codexmonitor) — Homebrew-installed helper to list/inspect/watch local OpenAI Codex sessions (CLI + VS Code).

### Bambu 3D Printer Control

**@tobiasbischoff** — `hardware` `3d-printing` `skill`

[ClawHub](https://clawhub.com/tobiasbischoff/bambu-cli) — Control and troubleshoot BambuLab printers: status, jobs, camera, AMS, calibration, and more.

## Automation & Workflows

### Winix Air Purifier Control

**@antonplex** — `automation` `hardware` `air-quality`

Claude Code discovered and confirmed the purifier controls, then OpenClaw takes over to manage room air quality.

### Couch Potato Dev Mode

**@davekiss** — `telegram` `website` `migration`

Rebuilt entire personal site via Telegram while watching Netflix — Notion to Astro, 18 posts migrated, DNS to Cloudflare. Never opened a laptop.

### Job Search Agent

**@attol8** — `automation` `api` `skill`

Searches job listings, matches against CV keywords, and returns relevant opportunities with links. Built in 30 minutes using JSearch API.

### Todoist Skill via Telegram

**@iamsubhrajyoti** — `automation` `todoist` `skill` `telegram`

[X post](https://x.com/iamsubhrajyoti/status/2009949389884920153) — Automated Todoist tasks and had OpenClaw generate the skill directly in Telegram chat.

### Slack Auto-Support

**@henrymascot** — `slack` `automation` `support`

Watches company Slack channel, responds helpfully, and forwards notifications to Telegram. Autonomously fixed a production bug in a deployed app without being asked.

## Knowledge & Memory

### WhatsApp Memory Vault

**Community** — `memory` `transcription` `indexing`

Ingests full WhatsApp exports, transcribes 1k+ voice notes, cross-checks with git logs, outputs linked markdown reports.

### Karakeep Semantic Search

**@jamesbrooksco** — `search` `vector` `bookmarks`

[GitHub](https://github.com/jamesbrooksco/karakeep-semantic-search) — Adds vector search to Karakeep bookmarks using Qdrant + OpenAI/Ollama embeddings.

## Infrastructure & Deployment

### Home Assistant Add-on

**@ngutman** — `homeassistant` `docker` `raspberry-pi`

[GitHub](https://github.com/ngutman/openclaw-ha-addon) — OpenClaw gateway running on Home Assistant OS with SSH tunnel support and persistent state.

### Home Assistant Skill

**ClawHub** — `homeassistant` `skill` `automation`

[ClawHub](https://clawhub.com/skills/homeassistant) — Control and automate Home Assistant devices via natural language.

### Nix Packaging

**@openclaw** — `nix` `packaging` `deployment`

[GitHub](https://github.com/openclaw/nix-openclaw) — Batteries-included nixified OpenClaw configuration for reproducible deployments.

## Multi-Agent Orchestration

### Kev's Dream Team (14+ Agents)

**@adam91holt** — `multi-agent` `orchestration` `architecture`

[GitHub](https://github.com/adam91holt/orchestrated-ai-articles) — 14+ agents under one gateway with Opus orchestrator delegating to Codex workers. Comprehensive technical write-up covering the Dream Team roster, model selection, sandboxing, webhooks, heartbeats, and delegation flows.

---

## Submit Your Project

Have something to share? We'd love to feature it!

1. **Share It** — Post in [#showcase on Discord](https://discord.gg/clawd) or [tweet @openclaw](https://x.com/openclaw)
2. **Include Details** — Tell us what it does, link to the repo/demo, share a screenshot if you have one
3. **Get Featured** — We'll add standout projects to this page
