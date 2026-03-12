---
title: Fly.io
description: Deploy OpenClaw on Fly.io
---

# Fly.io Deployment

**Goal:** OpenClaw Gateway running on a [Fly.io](https://fly.io) machine with persistent storage, automatic HTTPS, and Discord/channel access.

## What you need

- [flyctl CLI](https://fly.io/docs/hands-on/install-flyctl/) installed
- Fly.io account (free tier works)
- Model auth: Anthropic API key (or other provider keys)
- Channel credentials: Discord bot token, Telegram token, etc.

## Beginner quick path

1. Clone repo → customize `fly.toml`
2. Create app + volume → set secrets
3. Deploy with `fly deploy`
4. SSH in to create config or use Control UI

## 1) Create the Fly app

```bash
# Clone the repo
git clone https://github.com/openclaw/openclaw-python.git
cd openclaw-python

# Create a new Fly app (pick your own name)
fly apps create my-openclaw

# Create a persistent volume (1GB is usually enough)
fly volumes create openclaw_data --size 1 --region iad
```

**Tip:** Choose a region close to you. Common options: `lhr` (London), `iad` (Virginia), `sjc` (San Jose).

## 2) Configure fly.toml

Edit `fly.toml` to match your app name and requirements.

**Security note:** The default config exposes a public URL. For a hardened deployment with no public IP, see [Private Deployment](#private-deployment-hardened) or use `fly.private.toml`.

```toml
app = "my-openclaw"  # Your app name
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  PYTHONUNBUFFERED = "1"
  OPENCLAW_STATE_DIR = "/data"

[processes]
  app = "python -m openclaw gateway run --allow-unconfigured --port 3000 --bind lan"

[http_service]
  internal_port = 3000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1
  processes = ["app"]

[[vm]]
  size = "shared-cpu-2x"
  memory = "2048mb"

[mounts]
  source = "openclaw_data"
  destination = "/data"
```

**Key settings:**

| Setting                        | Why                                                                         |
| ------------------------------ | --------------------------------------------------------------------------- |
| `--bind lan`                   | Binds to `0.0.0.0` so Fly's proxy can reach the gateway                     |
| `--allow-unconfigured`         | Starts without a config file (you'll create one after)                      |
| `internal_port = 3000`         | Must match `--port 3000` (or `OPENCLAW_GATEWAY_PORT`) for Fly health checks |
| `memory = "2048mb"`            | 512MB is too small; 2GB recommended                                         |
| `OPENCLAW_STATE_DIR = "/data"` | Persists state on the volume                                                |

## 3) Set secrets

```bash
# Required: Gateway token (for non-loopback binding)
fly secrets set OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)

# Model provider API keys
fly secrets set ANTHROPIC_API_KEY=sk-ant-...

# Optional: Other providers
fly secrets set OPENAI_API_KEY=sk-...

# Channel tokens
fly secrets set DISCORD_BOT_TOKEN=MTQ...
```

## 4) Deploy

```bash
fly deploy
```

First deploy builds the Docker image (~2-3 minutes). Subsequent deploys are faster.

After deployment, verify:

```bash
fly status
fly logs
```

## 5) Create config file

SSH into the machine to create a proper config:

```bash
fly ssh console
```

Create the config directory and file:

```bash
mkdir -p /data
cat > /data/openclaw.json << 'EOF'
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-6"
      }
    }
  },
  "gateway": {
    "mode": "local",
    "bind": "auto"
  }
}
EOF
```

Restart to apply:

```bash
exit
fly machine restart <machine-id>
```

## 6) Access the Gateway

### Control UI

```bash
fly open
```

Or visit `https://my-openclaw.fly.dev/`

### Logs

```bash
fly logs              # Live logs
fly logs --no-tail    # Recent logs
```

### SSH Console

```bash
fly ssh console
```

## Troubleshooting

### "App is not listening on expected address"

The gateway is binding to `127.0.0.1` instead of `0.0.0.0`.

**Fix:** Add `--bind lan` to your process command in `fly.toml`.

### Health checks failing / connection refused

**Fix:** Ensure `internal_port` matches the gateway port.

### OOM / Memory Issues

**Fix:** Increase memory in `fly.toml`:

```toml
[[vm]]
  memory = "2048mb"
```

## Updates

```bash
# Pull latest changes
git pull

# Redeploy
fly deploy

# Check health
fly status
fly logs
```

## Private Deployment (Hardened)

For a hardened deployment with **no public exposure**, use the private template:

```bash
fly deploy -c fly.private.toml
```

### Accessing a private deployment

**Option 1: Local proxy (simplest)**

```bash
fly proxy 3000:3000 -a my-openclaw
# Then open http://localhost:3000 in browser
```

**Option 2: SSH only**

```bash
fly ssh console -a my-openclaw
```

## Notes

- Fly.io uses **x86 architecture** (not ARM)
- For WhatsApp/Telegram onboarding, use `fly ssh console`
- Persistent data lives on the volume at `/data`

## Cost

With the recommended config (`shared-cpu-2x`, 2GB RAM):

- ~$10-15/month depending on usage
- Free tier includes some allowance

See [Fly.io pricing](https://fly.io/docs/about/pricing/) for details.
