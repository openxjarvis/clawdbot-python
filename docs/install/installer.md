---
summary: "How the installer scripts work (install.sh, install.ps1), flags, and automation"
read_when:
  - You want to understand `openclaw.ai/install.sh`
  - You want to automate installs (CI / headless)
  - You want to install from a GitHub checkout
title: "Installer Internals"
---

# Installer internals

OpenClaw Python ships installer scripts for automated setup.

| Script                             | Platform             | What it does                                                                                 |
| ---------------------------------- | -------------------- | -------------------------------------------------------------------------------------------- |
| [`install.sh`](#installsh)         | macOS / Linux / WSL  | Installs Python if needed, installs OpenClaw via pip (default) or git, and can run onboarding. |
| [`install.ps1`](#installps1)       | Windows (PowerShell) | Installs Python if needed, installs OpenClaw via pip (default) or git, and can run onboarding. |

## Quick commands

**install.sh:**

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash
```

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --help
```

**install.ps1:**

```powershell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

> If install succeeds but `openclaw` is not found in a new terminal, see [Python troubleshooting](/install/python#troubleshooting).

---

## install.sh

Recommended for most interactive installs on macOS/Linux/WSL.

### Flow (install.sh)

1. **Detect OS** — Supports macOS and Linux (including WSL). If macOS is detected, installs Homebrew if missing.
2. **Ensure Python 3.11+** — Checks Python version and installs Python 3.11 if needed.
3. **Ensure Git** — Installs Git if missing.
4. **Install OpenClaw** — `pip` method (default): `pip install openclaw-python`; `git` method: clone/update repo, install with pip, then install wrapper at `~/.local/bin/openclaw`
5. **Post-install tasks** — Runs `openclaw doctor --non-interactive` on upgrades and git installs; attempts onboarding when appropriate.

### Examples (install.sh)

Default:

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash
```

Skip onboarding:

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --no-onboard
```

Git install:

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --install-method git
```

Dry run:

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --dry-run
```

### Flags reference

| Flag                            | Description                                                |
| ------------------------------- | ---------------------------------------------------------- |
| `--install-method pip\|git`     | Choose install method (default: `pip`). Alias: `--method`  |
| `--pip`                         | Shortcut for pip method                                    |
| `--git`                         | Shortcut for git method. Alias: `--github`                 |
| `--version <version>`           | pip version or pre-release (default: `latest`)             |
| `--beta`                        | Use pre-release if available, else fallback to `latest`    |
| `--git-dir <path>`              | Checkout directory (default: `~/openclaw`). Alias: `--dir` |
| `--no-git-update`               | Skip `git pull` for existing checkout                      |
| `--no-prompt`                   | Disable prompts                                            |
| `--no-onboard`                  | Skip onboarding                                            |
| `--onboard`                     | Enable onboarding                                          |
| `--dry-run`                     | Print actions without applying changes                     |
| `--verbose`                     | Enable debug output                                        |
| `--help`                        | Show usage (`-h`)                                          |

### Environment variables reference

| Variable                                    | Description                                   |
| ------------------------------------------- | --------------------------------------------- |
| `OPENCLAW_INSTALL_METHOD=pip\|git`          | Install method                                |
| `OPENCLAW_VERSION=latest\|<semver>`         | pip version or tag                            |
| `OPENCLAW_BETA=0\|1`                        | Use pre-release if available                  |
| `OPENCLAW_GIT_DIR=<path>`                   | Checkout directory                            |
| `OPENCLAW_GIT_UPDATE=0\|1`                  | Toggle git updates                            |
| `OPENCLAW_NO_PROMPT=1`                      | Disable prompts                               |
| `OPENCLAW_NO_ONBOARD=1`                     | Skip onboarding                               |
| `OPENCLAW_DRY_RUN=1`                        | Dry run mode                                  |
| `OPENCLAW_VERBOSE=1`                        | Debug mode                                    |

---

## install.ps1

### Flow (install.ps1)

1. **Ensure PowerShell + Windows environment** — Requires PowerShell 5+.
2. **Ensure Python 3.11+** — If missing, attempts install via winget, then Chocolatey, then Scoop.
3. **Install OpenClaw** — `pip` method (default): `pip install openclaw-python`; `git` method: clone/update repo, install with pip.
4. **Post-install tasks** — Adds needed bin directory to user PATH when possible, then runs `openclaw doctor --non-interactive`.

### Examples (install.ps1)

Default:

```powershell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

Git install:

```powershell
& ([scriptblock]::Create((iwr -useb https://openclaw.ai/install.ps1))) -InstallMethod git
```

Dry run:

```powershell
& ([scriptblock]::Create((iwr -useb https://openclaw.ai/install.ps1))) -DryRun
```

### Flags reference

| Flag                      | Description                                            |
| ------------------------- | ------------------------------------------------------ |
| `-InstallMethod pip\|git` | Install method (default: `pip`)                        |
| `-Tag <tag>`              | pip version (default: `latest`)                        |
| `-GitDir <path>`          | Checkout directory (default: `%USERPROFILE%\openclaw`) |
| `-NoOnboard`              | Skip onboarding                                        |
| `-NoGitUpdate`            | Skip `git pull`                                        |
| `-DryRun`                 | Print actions only                                     |

---

## CI and automation

Use non-interactive flags/env vars for predictable runs.

Non-interactive pip install:

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --no-prompt --no-onboard
```

Non-interactive git install:

```bash
OPENCLAW_INSTALL_METHOD=git OPENCLAW_NO_PROMPT=1 \
  curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash
```

---

## Troubleshooting

**Why is Git required?**
Git is required for the `git` install method. For `pip` installs, Git is still checked/installed to avoid dependency installation failures when packages use git URLs.

**Why does pip hit permission errors on Linux?**
Some Linux setups point pip global install to root-owned paths. Use `pip install --user openclaw-python` and append `~/.local/bin` to your PATH.

**openclaw not found after install**
Usually a PATH issue. Make sure `~/.local/bin` (Linux/macOS) is in your PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add this line to your `~/.bashrc` or `~/.zshrc` to make it permanent.
