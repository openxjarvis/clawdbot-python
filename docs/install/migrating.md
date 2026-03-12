---
summary: "Move (migrate) a OpenClaw install from one machine to another"
read_when:
  - You are moving OpenClaw to a new laptop/server
  - You want to preserve sessions, auth, and channel logins (WhatsApp, etc.)
title: "Migration Guide"
---

# Migrating OpenClaw to a new machine

This guide migrates a OpenClaw Gateway from one machine to another **without redoing onboarding**.

The migration is simple conceptually:

- Copy the **state directory** (`$OPENCLAW_STATE_DIR`, default: `~/.openclaw/`) — this includes config, auth, sessions, and channel state.
- Copy your **workspace** (`~/.openclaw/workspace/` by default) — this includes your agent files (memory, prompts, etc.).

But there are common footguns around **profiles**, **permissions**, and **partial copies**.

## Before you start (what you are migrating)

### 1) Identify your state directory

Most installs use the default:

- **State dir:** `~/.openclaw/`

But it may be different if you use:

- `--profile <name>` (often becomes `~/.openclaw-<profile>/`)
- `OPENCLAW_STATE_DIR=/some/path`

If you're not sure, run on the **old** machine:

```bash
openclaw status
```

### 2) Identify your workspace

Common defaults:

- `~/.openclaw/workspace/` (recommended workspace)
- a custom folder you created

### 3) Understand what you will preserve

If you copy **both** the state dir and workspace, you keep:

- Gateway configuration (`openclaw.json`)
- Auth profiles / API keys / OAuth tokens
- Session history + agent state
- Channel state (e.g. WhatsApp login/session)
- Your workspace files (memory, skills notes, etc.)

## Migration steps (recommended)

### Step 0 — Make a backup (old machine)

On the **old** machine, stop the gateway first:

```bash
openclaw gateway stop
```

Archive the state dir and workspace:

```bash
cd ~
tar -czf openclaw-state.tgz .openclaw
tar -czf openclaw-workspace.tgz .openclaw/workspace
```

### Step 1 — Install OpenClaw on the new machine

On the **new** machine, install the CLI:

```bash
pip install openclaw-python
```

See: [Install](/install)

### Step 2 — Copy the state dir + workspace to the new machine

Copy **both**:

- `$OPENCLAW_STATE_DIR` (default `~/.openclaw/`)
- your workspace (default `~/.openclaw/workspace/`)

Common approaches:

- `scp` the tarballs and extract
- `rsync -a` over SSH
- external drive

After copying, ensure:

- Hidden directories were included (e.g. `.openclaw/`)
- File ownership is correct for the user running the gateway

### Step 3 — Run Doctor (migrations + service repair)

On the **new** machine:

```bash
openclaw doctor
```

Doctor is the "safe boring" command. It repairs services, applies config migrations, and warns about mismatches.

Then:

```bash
openclaw gateway restart
openclaw status
```

## Common footguns (and how to avoid them)

### Footgun: profile / state-dir mismatch

If you ran the old gateway with a profile (or `OPENCLAW_STATE_DIR`), and the new gateway uses a different one, you'll see symptoms like:

- config changes not taking effect
- channels missing / logged out
- empty session history

Fix: run the gateway/service using the **same** profile/state dir you migrated.

### Footgun: copying only `openclaw.json`

`openclaw.json` is not enough. Many providers store state under:

- `$OPENCLAW_STATE_DIR/credentials/`
- `$OPENCLAW_STATE_DIR/agents/<agentId>/...`

Always migrate the entire `$OPENCLAW_STATE_DIR` folder.

### Footgun: permissions / ownership

If you copied as root or changed users, the gateway may fail to read credentials/sessions.

Fix: ensure the state dir + workspace are owned by the user running the gateway.

### Footgun: secrets in backups

`$OPENCLAW_STATE_DIR` contains secrets (API keys, OAuth tokens, WhatsApp creds). Treat backups like production secrets:

- store encrypted
- avoid sharing over insecure channels
- rotate keys if you suspect exposure

## Verification checklist

On the new machine, confirm:

- `openclaw status` shows the gateway running
- Your channels are still connected (e.g. WhatsApp doesn't require re-pair)
- The dashboard opens and shows existing sessions
- Your workspace files (memory, configs) are present

## Related

- [Doctor](/gateway/doctor)
- [Gateway troubleshooting](/gateway/troubleshooting)
- [Where does OpenClaw store its data?](/help/faq#where-does-openclaw-store-its-data)
