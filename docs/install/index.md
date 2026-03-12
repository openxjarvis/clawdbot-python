---
summary: "Installing OpenClaw Python (pip, Docker, from source)"
read_when:
  - Installing OpenClaw Python for the first time
  - Upgrading or running from source
title: "Installation"
---

# Installation

## Requirements

- Python 3.11+
- pip 23+ (recommended)

## Install from PyPI (recommended)

```bash
pip install openclaw-python
```

## Setup

After installing, run the setup wizard to create your config:

```bash
openclaw setup
```

This creates `~/.openclaw/openclaw.json` with sensible defaults and initializes
the workspace directory.

## Start the gateway

```bash
openclaw start
```

## Docker

```dockerfile
FROM python:3.12-slim

RUN pip install openclaw-python

COPY openclaw.json /root/.openclaw/openclaw.json

CMD ["openclaw", "start"]
```

```bash
docker run -v ~/.openclaw:/root/.openclaw openclaw
```

## Docker Compose

```yaml
version: "3.9"
services:
  openclaw:
    image: python:3.12-slim
    command: bash -c "pip install openclaw-python && openclaw start"
    volumes:
      - ./openclaw.json:/root/.openclaw/openclaw.json
      - openclaw-data:/root/.openclaw
    ports:
      - "8080:8080"
    restart: unless-stopped

volumes:
  openclaw-data:
```

## Install from source

```bash
git clone https://github.com/openxjarvis/openclaw-python
cd openclaw-python
pip install -e ".[dev]"
openclaw setup
```

## Upgrade

```bash
pip install --upgrade openclaw-python
```

## Uninstall

```bash
pip uninstall openclaw-python
rm -rf ~/.openclaw   # WARNING: deletes config, sessions, memory
```

## Systemd service

```ini
[Unit]
Description=OpenClaw Python Gateway
After=network.target

[Service]
Type=simple
User=myuser
ExecStart=/usr/local/bin/openclaw start
Restart=on-failure
RestartSec=5s
WorkingDirectory=/home/myuser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now openclaw
```
