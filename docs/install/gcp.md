---
summary: "Run OpenClaw Gateway 24/7 on a GCP Compute Engine VM (Docker) with durable state"
read_when:
  - You want OpenClaw running 24/7 on GCP
  - You want a production-grade, always-on Gateway on your own VM
  - You want full control over persistence, binaries, and restart behavior
title: "GCP"
---

# OpenClaw on GCP Compute Engine (Docker, Production VPS Guide)

## Goal

Run a persistent OpenClaw Gateway on a GCP Compute Engine VM using Docker, with durable state, baked-in binaries, and safe restart behavior.

If you want "OpenClaw 24/7 for ~$5-12/mo", this is a reliable setup on Google Cloud.

## What are we doing (simple terms)?

- Create a GCP project and enable billing
- Create a Compute Engine VM
- Install Docker (isolated app runtime)
- Start the OpenClaw Gateway in Docker
- Persist `~/.openclaw` + `~/.openclaw/workspace` on the host (survives restarts/rebuilds)
- Access the Control UI from your laptop via an SSH tunnel

This guide uses Debian on GCP Compute Engine.

---

## What you need

- GCP account (free tier eligible for e2-micro)
- gcloud CLI installed (or use Cloud Console)
- SSH access from your laptop
- Basic comfort with SSH + copy/paste
- ~20-30 minutes
- Docker and Docker Compose
- Model auth credentials

---

## 1) Install gcloud CLI (or use Console)

Install from [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)

Initialize and authenticate:

```bash
gcloud init
gcloud auth login
```

---

## 2) Create a GCP project

```bash
gcloud projects create my-openclaw-project --name="OpenClaw Gateway"
gcloud config set project my-openclaw-project
```

Enable billing and the Compute Engine API:

```bash
gcloud services enable compute.googleapis.com
```

---

## 3) Create the VM

**Machine types:**

| Type     | Specs                    | Cost               | Notes              |
| -------- | ------------------------ | ------------------ | ------------------ |
| e2-small | 2 vCPU, 2GB RAM          | ~$12/mo            | Recommended        |
| e2-micro | 2 vCPU (shared), 1GB RAM | Free tier eligible | May OOM under load |

**CLI:**

```bash
gcloud compute instances create openclaw-gateway \
  --zone=us-central1-a \
  --machine-type=e2-small \
  --boot-disk-size=20GB \
  --image-family=debian-12 \
  --image-project=debian-cloud
```

---

## 4) SSH into the VM

```bash
gcloud compute ssh openclaw-gateway --zone=us-central1-a
```

---

## 5) Install Docker (on the VM)

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Log out and back in, then verify:

```bash
docker --version
docker compose version
```

---

## 6) Clone the OpenClaw repository

```bash
git clone https://github.com/openclaw/openclaw-python.git
cd openclaw-python
```

---

## 7) Create persistent host directories

```bash
mkdir -p ~/.openclaw
mkdir -p ~/.openclaw/workspace
```

---

## 8) Configure environment variables

Create `.env` in the repository root.

```bash
OPENCLAW_IMAGE=openclaw:latest
OPENCLAW_GATEWAY_TOKEN=change-me-now
OPENCLAW_GATEWAY_BIND=lan
OPENCLAW_GATEWAY_PORT=18789

OPENCLAW_CONFIG_DIR=/home/$USER/.openclaw
OPENCLAW_WORKSPACE_DIR=/home/$USER/.openclaw/workspace
```

Generate strong secrets:

```bash
openssl rand -hex 32
```

**Do not commit this file.**

---

## 9) Docker Compose configuration

Create or update `docker-compose.yml`.

```yaml
services:
  openclaw-gateway:
    image: ${OPENCLAW_IMAGE}
    build: .
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - PYTHONUNBUFFERED=1
      - OPENCLAW_GATEWAY_BIND=${OPENCLAW_GATEWAY_BIND}
      - OPENCLAW_GATEWAY_PORT=${OPENCLAW_GATEWAY_PORT}
      - OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN}
    volumes:
      - ${OPENCLAW_CONFIG_DIR}:/home/user/.openclaw
      - ${OPENCLAW_WORKSPACE_DIR}:/home/user/.openclaw/workspace
    ports:
      - "127.0.0.1:${OPENCLAW_GATEWAY_PORT}:18789"
    command:
      [
        "python",
        "-m",
        "openclaw",
        "gateway",
        "run",
        "--bind",
        "${OPENCLAW_GATEWAY_BIND}",
        "--port",
        "${OPENCLAW_GATEWAY_PORT}",
      ]
```

---

## 10) Bake required binaries into the image (critical)

Installing binaries inside a running container is a trap. All external binaries required by skills must be installed at image build time.

**Example Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y git curl socat && rm -rf /var/lib/apt/lists/*

# Example binary 1: Gmail CLI
RUN curl -L https://github.com/steipete/gog/releases/latest/download/gog_Linux_x86_64.tar.gz \
  | tar -xz -C /usr/local/bin && chmod +x /usr/local/bin/gog

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "openclaw"]
```

---

## 11) Build and launch

```bash
docker compose build
docker compose up -d openclaw-gateway
```

---

## 12) Verify Gateway

```bash
docker compose logs -f openclaw-gateway
```

Success:

```
[gateway] listening on ws://0.0.0.0:18789
```

---

## 13) Access from your laptop

Create an SSH tunnel to forward the Gateway port:

```bash
gcloud compute ssh openclaw-gateway --zone=us-central1-a -- -L 18789:127.0.0.1:18789
```

Open in your browser: `http://127.0.0.1:18789/`

---

## What persists where (source of truth)

| Component           | Location                          | Persistence mechanism  |
| ------------------- | --------------------------------- | ---------------------- |
| Gateway config      | `/home/user/.openclaw/`           | Host volume mount      |
| Model auth profiles | `/home/user/.openclaw/`           | Host volume mount      |
| Agent workspace     | `/home/user/.openclaw/workspace/` | Host volume mount      |
| External binaries   | `/usr/local/bin/`                 | Docker image           |
| Python runtime      | Container filesystem              | Docker image           |

---

## Updates

```bash
cd ~/openclaw-python
git pull
docker compose build
docker compose up -d
```

---

## Next steps

- Set up messaging channels: [Channels](/channels)
- Pair local devices as nodes: [Nodes](/nodes)
- Configure the Gateway: [Gateway configuration](/gateway/configuration)
