---
summary: "Stable, beta, and dev channels: semantics, switching, and tagging"
read_when:
  - You want to switch between stable/beta/dev
  - You are tagging or publishing prereleases
title: "Development Channels"
---

# Development channels

Last updated: 2026-01-21

OpenClaw ships three update channels:

- **stable**: PyPI dist-tag `latest`.
- **beta**: PyPI pre-release (builds under test).
- **dev**: moving head of `main` (git). PyPI pre-release when published.

We ship builds to **beta**, test them, then **promote a vetted build to `latest`**
without changing the version number — PyPI releases are the source of truth for pip installs.

## Switching channels

Git checkout:

```bash
openclaw update --channel stable
openclaw update --channel beta
openclaw update --channel dev
```

- `stable`/`beta` check out the latest matching tag (often the same tag).
- `dev` switches to `main` and rebases on the upstream.

pip install:

```bash
pip install openclaw-python          # stable
pip install openclaw-python --pre    # beta/dev pre-releases
```

When you **explicitly** switch channels with `--channel`, OpenClaw also aligns
the install method:

- `dev` ensures a git checkout (default `~/openclaw`, override with `OPENCLAW_GIT_DIR`),
  updates it, and installs the global CLI from that checkout.
- `stable`/`beta` installs from PyPI using the matching release.

Tip: if you want stable + dev in parallel, keep two clones and point your gateway at the stable one.

## Plugins and channels

When you switch channels with `openclaw update`, OpenClaw also syncs plugin sources:

- `dev` prefers bundled plugins from the git checkout.
- `stable` and `beta` restore pip-installed plugin packages.

## Tagging best practices

- Tag releases you want git checkouts to land on (`vYYYY.M.D` or `vYYYY.M.D-<patch>`).
- Keep tags immutable: never move or reuse a tag.
- PyPI releases remain the source of truth for pip installs:
  - `latest` → stable
  - pre-release → candidate build
  - `dev` → main snapshot (optional)

## macOS app availability

Beta and dev builds may **not** include a macOS app release. That's OK:

- The git tag and PyPI release can still be published.
- Call out "no macOS build for this beta" in release notes or changelog.
