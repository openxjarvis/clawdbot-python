---
name: uv
description: "Install and use uv — the fast Python package and project manager. Use when: user needs to install uv, manage Python versions, create virtual environments, install packages/tools, run Python scripts with inline deps, or set up any Python-based skill that requires uv. uv is the standard Python tool manager for this OpenClaw installation."
homepage: https://docs.astral.sh/uv/
metadata:
  {
    "openclaw":
      {
        "emoji": "🐍",
        "always": true,
        "install":
          [
            {
              "id": "brew",
              "kind": "brew",
              "formula": "uv",
              "bins": ["uv"],
              "label": "Install uv (brew)",
            },
          ],
      },
  }
---

# uv — Python Package & Project Manager

`uv` is a fast, all-in-one Python tool manager (replaces pip, pip-tools, pipx, pyenv, virtualenv). It is required by many OpenClaw skills that run Python scripts or install Python CLI tools.

## Check if uv is installed

```bash
uv --version
```

---

## Install uv (if not present)

### macOS / Linux (recommended)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After install, reload PATH:

```bash
source ~/.bashrc 2>/dev/null || source ~/.zshrc 2>/dev/null || export PATH="$HOME/.cargo/bin:$PATH"
```

### macOS via Homebrew

```bash
brew install uv
```

### pip (if Python already available)

```bash
pip install uv
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify install:

```bash
uv --version
```

---

## Install Python CLI Tools (`uv tool install`)

Use for tools that expose a command-line binary (nano-pdf, ruff, etc.):

```bash
# Install a tool globally (available system-wide)
uv tool install nano-pdf
uv tool install ruff
uv tool install httpie

# Install a specific version
uv tool install nano-pdf==0.3.1

# List installed tools
uv tool list

# Upgrade a tool
uv tool upgrade nano-pdf

# Uninstall a tool
uv tool uninstall nano-pdf
```

---

## Install Packages (`uv pip install`)

Drop-in replacement for `pip install`, uses the active virtual environment:

```bash
# Install a package
uv pip install requests
uv pip install "python-pptx>=0.6.23"

# Install from requirements file
uv pip install -r requirements.txt

# Install current project in editable mode
uv pip install -e .

# Show installed package info
uv pip show requests

# List all installed packages
uv pip list

# Uninstall
uv pip uninstall requests
```

---

## Run Scripts (`uv run`)

Run a Python script without manually activating a venv. Handles dependencies automatically:

```bash
# Run a script directly
uv run script.py

# Run with extra packages (inline, no venv needed)
uv run --with requests script.py
uv run --with "requests>=2.28" --with pillow script.py

# Run a module
uv run -m http.server 8080

# Run with a specific Python version
uv run --python 3.12 script.py
```

For scripts with inline dependency metadata (PEP 723):

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "pillow"]
# ///
import requests
...
```

```bash
uv run script.py  # auto-installs requests and pillow
```

---

## Manage Python Versions

```bash
# Install a specific Python version
uv python install 3.12
uv python install 3.11 3.12 3.13

# List installed Python versions
uv python list

# Pin Python version for current project
uv python pin 3.12
```

---

## Virtual Environments

```bash
# Create a virtual environment
uv venv                    # creates .venv in current dir
uv venv myenv              # custom name
uv venv --python 3.12      # specific Python version

# Activate (standard shell activation)
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows

# Install packages into the venv
uv pip install requests
```

---

## Project Management (`uv sync` / `uv add`)

For projects with `pyproject.toml`:

```bash
# Sync all dependencies from lockfile
uv sync

# Add a dependency
uv add requests
uv add "fastapi>=0.100"

# Add a dev dependency
uv add --dev pytest

# Remove a dependency
uv remove requests

# Lock without installing
uv lock
```

---

## Common Patterns for OpenClaw Skills

### Run a skill script with dependencies

```bash
uv run {skillDir}/scripts/my_script.py --arg value
```

### Install a Python skill tool then run it

```bash
uv tool install nano-pdf
nano-pdf ...
```

### Quick one-off script with packages

```bash
uv run --with httpx --with rich python3 -c "
import httpx, rich
r = httpx.get('https://api.github.com')
rich.print(r.json())
"
```

---

## Troubleshooting

**`uv: command not found` after install:**

```bash
# Add uv to PATH manually
export PATH="$HOME/.cargo/bin:$PATH"          # curl install default location
export PATH="$HOME/.local/bin:$PATH"          # some Linux distros
# Then add to shell profile permanently:
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.zshrc
```

**`uv tool install` binary not found after install:**

```bash
# uv tool binaries live in:
uv tool dir --bin   # shows the bin directory
# Ensure it's in PATH:
export PATH="$(uv tool dir --bin):$PATH"
```

**Permission error on Linux:**

```bash
# Run with user install (no sudo needed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# uv always installs to user space (~/.cargo/bin), never needs sudo
```

**Slow install / behind proxy:**

```bash
UV_HTTP_TIMEOUT=120 uv tool install nano-pdf
```
