---
title: "Python"
summary: "Install and configure Python for OpenClaw — version requirements, install options, and PATH troubleshooting"
read_when:
  - "You need to install Python before installing OpenClaw"
  - "You installed OpenClaw but `openclaw` is command not found"
  - "pip install fails with permissions or PATH issues"
---

# Python

OpenClaw requires **Python 3.11 or newer**. The [installer script](/install#install-methods) will detect and install Python automatically — this page is for when you want to set up Python yourself and make sure everything is wired up correctly (versions, PATH, global installs).

## Check your version

```bash
python --version
```

If this prints `3.11.x` or higher, you're good. If Python isn't installed or the version is too old, pick an install method below.

## Install Python

**macOS**

**Homebrew** (recommended):

```bash
brew install python
```

Or download the macOS installer from [python.org](https://www.python.org/).

**Linux — Ubuntu / Debian:**

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip python3-venv
```

**Linux — Fedora / RHEL:**

```bash
sudo dnf install python3.11
```

**Windows**

**winget** (recommended):

```powershell
winget install Python.Python.3.11
```

**Chocolatey:**

```powershell
choco install python311
```

Or download the Windows installer from [python.org](https://www.python.org/).

**Using a version manager (pyenv, mise, asdf)**

Version managers let you switch between Python versions easily. Popular options:

- [**pyenv**](https://github.com/pyenv/pyenv) — widely used on macOS/Linux
- [**mise**](https://mise.jdx.dev/) — polyglot (Python, Node, Ruby, etc.)

Example with pyenv:

```bash
pyenv install 3.11
pyenv global 3.11
```

Make sure your version manager is initialized in your shell startup file (`~/.zshrc` or `~/.bashrc`). If it isn't, `openclaw` may not be found in new terminal sessions because the PATH won't include Python's bin directory.

## Install OpenClaw

```bash
pip install openclaw-python
```

Or, to install for the current user only (no root required):

```bash
pip install --user openclaw-python
```

## Troubleshooting

### `openclaw: command not found`

This almost always means pip's user bin directory isn't on your PATH.

1. Find your user bin directory:

```bash
python -m site --user-base
```

The bin directory is `<user-base>/bin` on macOS/Linux or `<user-base>/Scripts` on Windows.

2. Add it to your shell startup file:

```bash
export PATH="$(python -m site --user-base)/bin:$PATH"
```

Then open a new terminal (or run `source ~/.zshrc`).

### Permission errors on `pip install` (Linux)

If you see `Permission denied` errors, use the `--user` flag:

```bash
pip install --user openclaw-python
```

Add `~/.local/bin` to your PATH to make the installed command accessible:

```bash
export PATH="$HOME/.local/bin:$PATH"
```
