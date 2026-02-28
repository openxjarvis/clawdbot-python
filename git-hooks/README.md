# git-hooks

Git hooks for the OpenClaw Python repository.

Mirrors: `openclaw/git-hooks/`

## pre-commit

Runs `ruff check --fix` (lint) and `ruff format` on all staged `.py` files before every commit.

### Install manually

```bash
cp git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Install via pre-commit framework

```bash
pip install pre-commit
pre-commit install
```

Then add `.pre-commit-config.yaml` to the repo root:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff lint
        entry: ruff check --fix
        language: system
        types: [python]
        pass_filenames: true
      - id: ruff-format
        name: ruff format
        entry: ruff format
        language: system
        types: [python]
        pass_filenames: true
```

### Requirements

- [ruff](https://docs.astral.sh/ruff/) (`pip install ruff` or `uv add ruff`)
