---
summary: "Overview of OpenClaw Python onboarding options and flows"
read_when:
  - Choosing an onboarding path
  - Setting up a new environment
title: "Onboarding Overview"
sidebarTitle: "Onboarding Overview"
---

# Onboarding Overview

OpenClaw Python supports multiple onboarding paths depending on where the Gateway runs
and how you prefer to configure providers.

## Choose your onboarding path

- **CLI wizard** for macOS, Linux, and Windows (via WSL2).
- **Non-interactive** for CI, scripts, and automated provisioning.

## CLI onboarding wizard

Run the wizard in a terminal:

```bash
openclaw onboard
```

Use the CLI wizard when you want full control of the Gateway, workspace,
channels, and skills. Docs:

- [Onboarding Wizard (CLI)](/start/wizard)
- [CLI Automation](/start/wizard-cli-automation)

## Custom Provider

If you need an endpoint that is not listed, including hosted providers that
expose standard OpenAI or Anthropic APIs, choose **Custom Provider** in the
CLI wizard. You will be asked to:

- Pick OpenAI-compatible, Anthropic-compatible, or **Unknown** (auto-detect).
- Enter a base URL and API key (if required by the provider).
- Provide a model ID and optional alias.
- Choose an Endpoint ID so multiple custom endpoints can coexist.

For detailed steps, follow the CLI onboarding docs above.

## Non-interactive setup

For scripted environments, use `--non-interactive` with `openclaw onboard`.
See [CLI Automation](/start/wizard-cli-automation) for examples.
