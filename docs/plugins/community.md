---
summary: "Community plugins: quality bar, hosting requirements, and submission path"
read_when:
  - You want to publish a third-party OpenClaw Python plugin
  - You want to propose a plugin for docs listing
title: "Community plugins"
---

# Community plugins

This page tracks high-quality **community-maintained plugins** for OpenClaw Python.

We accept PRs that add community plugins here when they meet the quality bar.

## Required for listing

- Plugin package is published on PyPI (installable via `pip install <package>`).
- Source code is hosted on GitHub (public repository).
- Repository includes setup/use docs and an issue tracker.
- Plugin has a clear maintenance signal (active maintainer, recent updates, or responsive issue handling).

## How to submit

Open a PR that adds your plugin to this page with:

- Plugin name
- PyPI package name
- GitHub repository URL
- One-line description
- Install command

## Review bar

We prefer plugins that are useful, documented, and safe to operate.
Low-effort wrappers, unclear ownership, or unmaintained packages may be declined.

## Candidate format

Use this format when adding entries:

- **Plugin Name** — short description
  pypi: `your-package-name`
  repo: `https://github.com/org/repo`
  install: `pip install your-package-name`
