"""Device pairing extension — QR-based device pairing and approval.

Mirrors TypeScript: openclaw/extensions/device-pair/index.ts
"""
from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import os
import socket
import subprocess
from typing import Any

DEFAULT_GATEWAY_PORT = 18789


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _is_private_ipv4(addr: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(addr)
        return ip.is_private
    except ValueError:
        return False


def _is_tailnet_ipv4(addr: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(addr)
        # Tailscale CGNAT range: 100.64.0.0/10
        net = ipaddress.IPv4Network("100.64.0.0/10")
        return ip in net
    except ValueError:
        return False


def _pick_matching_ipv4(predicate) -> str | None:
    try:
        hostname = socket.gethostname()
        addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for addr in addrs:
            ip = addr[4][0]
            if not ip.startswith("127.") and predicate(ip):
                return ip
    except Exception:
        pass
    # Try all interfaces
    try:
        import netifaces  # optional
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for a in addrs:
                ip = a.get("addr", "")
                if ip and not ip.startswith("127.") and predicate(ip):
                    return ip
    except ImportError:
        pass
    return None


def _pick_lan_ipv4() -> str | None:
    return _pick_matching_ipv4(_is_private_ipv4)


def _pick_tailnet_ipv4() -> str | None:
    return _pick_matching_ipv4(_is_tailnet_ipv4)


def _normalize_url(raw: str, scheme_fallback: str) -> str | None:
    from urllib.parse import urlparse
    trimmed = raw.strip()
    if not trimmed:
        return None
    try:
        parsed = urlparse(trimmed)
        scheme = parsed.scheme
        if scheme in ("http", ""):
            scheme = "ws"
        elif scheme == "https":
            scheme = "wss"
        if scheme not in ("ws", "wss"):
            return None
        host = parsed.hostname
        if not host:
            return None
        port = f":{parsed.port}" if parsed.port else ""
        return f"{scheme}://{host}{port}"
    except Exception:
        pass
    without_path = trimmed.split("/")[0]
    if not without_path:
        return None
    return f"{scheme_fallback}://{without_path}"


def _resolve_gateway_port(config: dict) -> int:
    env_raw = (
        os.environ.get("OPENCLAW_GATEWAY_PORT", "").strip()
        or os.environ.get("CLAWDBOT_GATEWAY_PORT", "").strip()
    )
    if env_raw:
        try:
            v = int(env_raw)
            if v > 0:
                return v
        except ValueError:
            pass
    gw = config.get("gateway") or {}
    port = gw.get("port")
    if isinstance(port, (int, float)) and port > 0:
        return int(port)
    return DEFAULT_GATEWAY_PORT


def _resolve_scheme(config: dict, force_secure: bool = False) -> str:
    if force_secure:
        return "wss"
    tls = ((config.get("gateway") or {}).get("tls") or {})
    return "wss" if tls.get("enabled") is True else "ws"


async def _resolve_tailnet_host(api) -> str | None:
    candidates = ["tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale"]
    for candidate in candidates:
        try:
            proc = await asyncio.create_subprocess_exec(
                candidate, "status", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            except TimeoutError:
                proc.kill()
                continue
            raw = stdout.decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            # Find JSON object in output
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end <= start:
                continue
            parsed = json.loads(raw[start:end + 1])
            self_entry = parsed.get("Self")
            if isinstance(self_entry, dict):
                dns = self_entry.get("DNSName", "")
                if dns:
                    return dns.rstrip(".")
                ips = self_entry.get("TailscaleIPs", [])
                if ips:
                    return ips[0]
        except (FileNotFoundError, PermissionError):
            continue
        except Exception:
            continue
    return None


async def _resolve_gateway_url(api) -> dict:
    """Resolve the public gateway URL. Returns {url?, source?, error?}."""
    raw_cfg = api.config or {}
    plugin_cfg = api.plugin_config or {}

    scheme = _resolve_scheme(raw_cfg)
    port = _resolve_gateway_port(raw_cfg)

    # 1. Explicit publicUrl from plugin config
    public_url = plugin_cfg.get("publicUrl", "")
    if isinstance(public_url, str) and public_url.strip():
        url = _normalize_url(public_url, scheme)
        if url:
            return {"url": url, "source": "plugins.entries.device-pair.config.publicUrl"}
        return {"error": "Configured publicUrl is invalid."}

    # 2. Tailscale serve/funnel
    gw = raw_cfg.get("gateway") or {}
    tailscale_mode = (gw.get("tailscale") or {}).get("mode", "off")
    if tailscale_mode in ("serve", "funnel"):
        host = await _resolve_tailnet_host(api)
        if not host:
            return {"error": "Tailscale Serve is enabled, but MagicDNS could not be resolved."}
        return {"url": f"wss://{host}", "source": f"gateway.tailscale.mode={tailscale_mode}"}

    # 3. Remote URL
    remote_url = (gw.get("remote") or {}).get("url", "")
    if isinstance(remote_url, str) and remote_url.strip():
        url = _normalize_url(remote_url, scheme)
        if url:
            return {"url": url, "source": "gateway.remote.url"}

    # 4. Bind mode
    bind = gw.get("bind", "loopback")
    if bind == "custom":
        host = (gw.get("customBindHost") or "").strip()
        if host:
            return {"url": f"{scheme}://{host}:{port}", "source": "gateway.bind=custom"}
        return {"error": "gateway.bind=custom requires gateway.customBindHost."}
    if bind == "tailnet":
        host = _pick_tailnet_ipv4()
        if host:
            return {"url": f"{scheme}://{host}:{port}", "source": "gateway.bind=tailnet"}
        return {"error": "gateway.bind=tailnet set, but no tailnet IP was found."}
    if bind == "lan":
        host = _pick_lan_ipv4()
        if host:
            return {"url": f"{scheme}://{host}:{port}", "source": "gateway.bind=lan"}
        return {"error": "gateway.bind=lan set, but no private LAN IP was found."}

    return {
        "error": (
            "Gateway is only bound to loopback. Set gateway.bind=lan, "
            "enable tailscale serve, or configure plugins.entries.device-pair.config.publicUrl."
        )
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _resolve_auth(config: dict) -> dict:
    """Resolve gateway auth token/password. Returns {token?, password?, label?, error?}."""
    gw_auth = (config.get("gateway") or {}).get("auth") or {}
    mode = gw_auth.get("mode", "")
    token = (
        os.environ.get("OPENCLAW_GATEWAY_TOKEN", "").strip()
        or os.environ.get("CLAWDBOT_GATEWAY_TOKEN", "").strip()
        or (gw_auth.get("token") or "").strip()
    )
    password = (
        os.environ.get("OPENCLAW_GATEWAY_PASSWORD", "").strip()
        or os.environ.get("CLAWDBOT_GATEWAY_PASSWORD", "").strip()
        or (gw_auth.get("password") or "").strip()
    )
    if mode == "password":
        if not password:
            return {"error": "Gateway auth is set to password, but no password is configured."}
        return {"password": password, "label": "password"}
    if mode == "token":
        if not token:
            return {"error": "Gateway auth is set to token, but no token is configured."}
        return {"token": token, "label": "token"}
    if token:
        return {"token": token, "label": "token"}
    if password:
        return {"password": password, "label": "password"}
    return {"error": "Gateway auth is not configured (no token or password)."}


# ---------------------------------------------------------------------------
# Setup code
# ---------------------------------------------------------------------------

def _encode_setup_code(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    return b64


def _format_setup_reply(payload: dict, auth_label: str) -> str:
    setup_code = _encode_setup_code(payload)
    return "\n".join([
        "Pairing setup code generated.",
        "",
        "1) Open the iOS app → Settings → Gateway",
        "2) Paste the setup code below and tap Connect",
        "3) Back here, run /pair approve",
        "",
        "Setup code:",
        setup_code,
        "",
        f"Gateway: {payload['url']}",
        f"Auth: {auth_label}",
    ])


def _format_setup_instructions() -> str:
    return "\n".join([
        "Pairing setup code generated.",
        "",
        "1) Open the iOS app → Settings → Gateway",
        "2) Paste the setup code from my next message and tap Connect",
        "3) Back here, run /pair approve",
    ])


# ---------------------------------------------------------------------------
# Pending requests formatting
# ---------------------------------------------------------------------------

def _format_pending_requests(pending: list) -> str:
    if not pending:
        return "No pending device pairing requests."
    lines = ["Pending device pairing requests:"]
    for req in pending:
        label = (req.get("displayName") or "").strip() or req.get("deviceId", "")
        platform = (req.get("platform") or "").strip()
        ip = (req.get("remoteIp") or "").strip()
        parts = [f"- {req.get('requestId', '')}"]
        if label:
            parts.append(f"name={label}")
        if platform:
            parts.append(f"platform={platform}")
        if ip:
            parts.append(f"ip={ip}")
        lines.append(" · ".join(parts))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# QR rendering (optional dependency)
# ---------------------------------------------------------------------------

def _render_qr_ascii(data: str) -> str | None:
    """Try to render a QR code as ASCII art. Returns None if no library found."""
    # Try segno (preferred)
    try:
        import io

        import segno
        qr = segno.make(data)
        buf = io.StringIO()
        qr.terminal(out=buf)
        return buf.getvalue()
    except ImportError:
        pass
    # Try qrcode
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(data)
        qr.make(fit=True)
        # Convert to ASCII
        import io
        buf = io.StringIO()
        qr.print_ascii(out=buf)
        return buf.getvalue()
    except ImportError:
        pass
    return None


# ---------------------------------------------------------------------------
# Node pairing wrappers
# ---------------------------------------------------------------------------

async def _list_device_pairing() -> dict:
    try:
        from openclaw.nodes.manager import get_node_manager
        manager = get_node_manager()
        pending_raw = manager.list_pending_pairs()
        paired_raw = manager.list_paired_nodes()
        # Normalize to dicts
        def _to_dict(obj):
            if isinstance(obj, dict):
                return obj
            return {
                "requestId": getattr(obj, "request_id", ""),
                "deviceId": getattr(obj, "node_id", ""),
                "displayName": getattr(obj, "display_name", None),
                "platform": getattr(obj, "platform", None),
                "remoteIp": None,
                "ts": getattr(obj, "requested_at", None),
            }
        pending = [_to_dict(p) for p in pending_raw]
        return {"pending": pending, "paired": paired_raw}
    except Exception as exc:
        return {"pending": [], "paired": [], "error": str(exc)}


async def _approve_device_pairing(request_id: str) -> dict | None:
    try:
        from openclaw.nodes.manager import get_node_manager
        manager = get_node_manager()
        result = manager.approve_pairing(request_id)
        if not result:
            return None
        if isinstance(result, dict):
            device_id = result.get("nodeId") or result.get("node_id") or request_id
            return {
                "device": {
                    "deviceId": device_id,
                    "displayName": result.get("displayName") or result.get("display_name"),
                    "platform": result.get("platform"),
                }
            }
        return {
            "device": {
                "deviceId": getattr(result, "node_id", request_id),
                "displayName": getattr(result, "display_name", None),
                "platform": getattr(result, "platform", None),
            }
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------

def register(api) -> None:
    from openclaw.plugins.types import OpenClawPluginCommandDefinition

    async def handle_pair(ctx) -> dict:
        args = (getattr(ctx, "args", None) or "").strip()
        tokens = [t for t in args.split() if t]
        action = (tokens[0].lower() if tokens else "")

        api.logger.info(
            f"device-pair: /pair invoked channel={getattr(ctx, 'channel', '?')} "
            f"sender={getattr(ctx, 'sender_id', None) or 'unknown'} "
            f"action={action or 'new'}"
        )

        # -- status / pending --
        if action in ("status", "pending"):
            result = await _list_device_pairing()
            return {"text": _format_pending_requests(result.get("pending", []))}

        # -- approve --
        if action == "approve":
            requested = tokens[1].strip() if len(tokens) > 1 else ""
            result = await _list_device_pairing()
            pending = result.get("pending", [])
            if not pending:
                return {"text": "No pending device pairing requests."}

            chosen = None
            if requested:
                if requested.lower() == "latest":
                    chosen = max(pending, key=lambda r: r.get("ts") or 0)
                else:
                    chosen = next((r for r in pending if r.get("requestId") == requested), None)
            elif len(pending) == 1:
                chosen = pending[0]
            else:
                return {
                    "text": (
                        f"{_format_pending_requests(pending)}\n\n"
                        "Multiple pending requests found. Approve one explicitly:\n"
                        "/pair approve <requestId>\n"
                        "Or approve the most recent:\n"
                        "/pair approve latest"
                    )
                }

            if not chosen:
                return {"text": "Pairing request not found."}

            approved = await _approve_device_pairing(chosen.get("requestId", ""))
            if not approved:
                return {"text": "Pairing request not found."}

            device = approved.get("device", {})
            label = (device.get("displayName") or "").strip() or device.get("deviceId", "")
            platform = (device.get("platform") or "").strip()
            platform_label = f" ({platform})" if platform else ""
            return {"text": f"\u2705 Paired {label}{platform_label}."}

        # -- resolve auth and URL for new pairing --
        auth = _resolve_auth(api.config or {})
        if auth.get("error"):
            return {"text": f"Error: {auth['error']}"}

        url_result = await _resolve_gateway_url(api)
        if not url_result.get("url"):
            return {"text": f"Error: {url_result.get('error', 'Gateway URL unavailable.')}"}

        payload: dict = {"url": url_result["url"]}
        if auth.get("token"):
            payload["token"] = auth["token"]
        if auth.get("password"):
            payload["password"] = auth["password"]

        # -- qr --
        if action == "qr":
            setup_code = _encode_setup_code(payload)
            qr_ascii = _render_qr_ascii(setup_code)
            auth_label = auth.get("label", "auth")

            channel = getattr(ctx, "channel", "")
            sender_id = (
                getattr(ctx, "sender_id", None)
                or getattr(ctx, "from_", None)
                or getattr(ctx, "to", None)
                or ""
            )
            sender_id = sender_id.strip() if sender_id else ""

            if channel == "telegram" and sender_id:
                try:
                    runtime = getattr(api, "runtime", None)
                    tg_send = (
                        getattr(getattr(getattr(runtime, "channel", None), "telegram", None), "send_message_telegram", None)
                        if runtime else None
                    )
                    if not tg_send:
                        from openclaw.channels.telegram.send_message import (
                            send_message_telegram as tg_send,
                        )
                    qr_text = "\n".join([
                        "Scan this QR code with the OpenClaw iOS app:",
                        "",
                        "```",
                        qr_ascii or setup_code,
                        "```",
                    ])
                    thread_id = getattr(ctx, "message_thread_id", None)
                    account_id = getattr(ctx, "account_id", None)
                    kwargs: dict[str, Any] = {}
                    if thread_id is not None:
                        kwargs["message_thread_id"] = thread_id
                    if account_id:
                        kwargs["account_id"] = account_id
                    await tg_send(sender_id, qr_text, **kwargs)
                    return {
                        "text": "\n".join([
                            f"Gateway: {payload['url']}",
                            f"Auth: {auth_label}",
                            "",
                            "After scanning, come back here and run `/pair approve` to complete pairing.",
                        ])
                    }
                except Exception as exc:
                    api.logger.warn(f"device-pair: telegram QR send failed, falling back ({exc})")

            info_lines = [
                f"Gateway: {payload['url']}",
                f"Auth: {auth_label}",
                "",
                "After scanning, run `/pair approve` to complete pairing.",
            ]
            if qr_ascii:
                return {
                    "text": "\n".join([
                        "Scan this QR code with the OpenClaw iOS app:",
                        "",
                        "```",
                        qr_ascii,
                        "```",
                        "",
                        *info_lines,
                    ])
                }
            return {
                "text": "\n".join([
                    "QR library not installed. Install with: pip install segno",
                    "",
                    "Setup code:",
                    setup_code,
                    "",
                    *info_lines,
                ])
            }

        # -- default: new pairing / setup code --
        auth_label = auth.get("label", "auth")
        channel = getattr(ctx, "channel", "")
        sender_id = (
            getattr(ctx, "sender_id", None)
            or getattr(ctx, "from_", None)
            or getattr(ctx, "to", None)
            or ""
        )
        sender_id = sender_id.strip() if sender_id else ""

        if channel == "telegram" and sender_id:
            try:
                from openclaw.channels.telegram.send_message import send_message_telegram as tg_send
                thread_id = getattr(ctx, "message_thread_id", None)
                account_id = getattr(ctx, "account_id", None)
                kwargs: dict[str, Any] = {}
                if thread_id is not None:
                    kwargs["message_thread_id"] = thread_id
                if account_id:
                    kwargs["account_id"] = account_id
                await tg_send(sender_id, _format_setup_instructions(), **kwargs)
                api.logger.info(
                    f"device-pair: telegram split send ok target={sender_id} "
                    f"account={account_id or 'none'} thread={thread_id or 'none'}"
                )
                return {"text": _encode_setup_code(payload)}
            except Exception as exc:
                api.logger.warn(
                    f"device-pair: telegram split send failed, falling back to single message ({exc})"
                )

        return {"text": _format_setup_reply(payload, auth_label)}

    api.register_command(OpenClawPluginCommandDefinition(
        name="pair",
        description="Generate setup codes and approve device pairing requests.",
        handler=handle_pair,
        accepts_args=True,
    ))


plugin = {
    "id": "device-pair",
    "name": "Device Pairing",
    "description": "Generate setup codes and approve device pairing requests.",
    "register": register,
}
