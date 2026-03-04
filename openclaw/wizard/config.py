"""Configuration wizards."""

from __future__ import annotations

from typing import Optional


async def configure_agent() -> dict:
    """Configure agent settings.
    
    Returns:
        Agent configuration
    """
    print("Agent Configuration")
    print("=" * 60)
    
    config = {}
    
    # Think level
    print("\nDefault think level:")
    print("  1. Low (fast, brief)")
    print("  2. Medium (balanced)")
    print("  3. High (thorough, detailed)")
    
    think_choice = input("Choose think level [2]: ").strip()
    if think_choice == "1":
        config["think_level"] = "low"
    elif think_choice == "3":
        config["think_level"] = "high"
    else:
        config["think_level"] = "medium"
    
    # Workspace
    workspace = input("\nWorkspace directory [./workspace]: ").strip()
    config["workspace"] = workspace or "./workspace"
    
    return config


def configure_telegram_enhanced() -> dict:
    """Configure Telegram with DM policy and environment variable support"""
    import os
    
    # Check environment variable
    env_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    token = None
    if env_token:
        use_env = input("Use TELEGRAM_BOT_TOKEN from environment? [Y/n]: ").strip().lower()
        if use_env != "n":
            token = env_token
            print("✓ Using token from environment")
    
    if not token:
        print("\nGet your bot token from @BotFather on Telegram:")
        print("  1. Open Telegram and search for @BotFather")
        print("  2. Send /newbot and follow instructions")
        print("  3. Copy the bot token\n")
        token = input("Telegram bot token: ").strip()
    
    if not token:
        return {}
    
    # DM policy
    print("\nDM Policy (who can message your bot):")
    print("  1. Open - Allow all users")
    print("  2. Pairing - Require approval (recommended)")
    print("  3. Allowlist - Specific users only")
    
    policy_choice = input("Choose DM policy [2]: ").strip()
    if policy_choice == "1":
        dm_policy = "open"
    elif policy_choice == "3":
        dm_policy = "allowlist"
    else:
        dm_policy = "pairing"
    
    config = {
        "enabled": True,
        "bot_token": token,
        "dm_policy": dm_policy,
        # TS defaults — align with openclaw TS openclaw.json
        "group_policy": "allowlist",
        "stream_mode": "partial",
    }

    # Allowlist
    if dm_policy == "allowlist":
        print("\nEnter allowed Telegram user IDs (comma-separated)")
        print("Find your ID by messaging the bot and checking logs")
        allow_from = input("Allowed user IDs: ").strip()
        if allow_from:
            config["allow_from"] = [x.strip() for x in allow_from.split(",")]

    return config


def configure_discord_enhanced() -> dict:
    """Configure Discord with enhanced options"""
    import os
    
    # Check environment variable
    env_token = os.getenv("DISCORD_BOT_TOKEN")
    
    token = None
    if env_token:
        use_env = input("Use DISCORD_BOT_TOKEN from environment? [Y/n]: ").strip().lower()
        if use_env != "n":
            token = env_token
            print("✓ Using token from environment")
    
    if not token:
        print("\nGet your bot token from Discord Developer Portal:")
        print("  1. Go to https://discord.com/developers/applications")
        print("  2. Create a new application or select existing")
        print("  3. Go to Bot section and copy the token\n")
        token = input("Discord bot token: ").strip()
    
    if not token:
        return {}
    
    # DM policy
    print("\nDM Policy:")
    print("  1. Open - Allow all users")
    print("  2. Pairing - Require approval (recommended)")
    
    policy_choice = input("Choose DM policy [2]: ").strip()
    dm_policy = "open" if policy_choice == "1" else "pairing"
    
    return {
        "enabled": True,
        "bot_token": token,
        "dm_policy": dm_policy,
    }


def configure_feishu_enhanced() -> dict:
    """Configure Feishu / Lark with App credentials and DM policy."""
    import os

    print("\nGet your Feishu / Lark app credentials from the Feishu Open Platform:")
    print("  1. Visit https://open.feishu.cn/app (or open.larksuite.com for Lark)")
    print("  2. Create or select your app")
    print("  3. Go to Credentials & Basic Info to copy App ID and App Secret\n")

    env_app_id = os.getenv("FEISHU_APP_ID") or os.getenv("LARK_APP_ID")
    env_app_secret = os.getenv("FEISHU_APP_SECRET") or os.getenv("LARK_APP_SECRET")

    if env_app_id:
        use_env = input(f"Use FEISHU_APP_ID ({env_app_id[:8]}…) from environment? [Y/n]: ").strip().lower()
        app_id = env_app_id if use_env != "n" else input("Feishu App ID: ").strip()
    else:
        app_id = input("Feishu App ID: ").strip()

    if not app_id:
        return {}

    if env_app_secret and env_app_id == app_id:
        use_env = input("Use FEISHU_APP_SECRET from environment? [Y/n]: ").strip().lower()
        app_secret = env_app_secret if use_env != "n" else input("Feishu App Secret: ").strip()
    else:
        app_secret = input("Feishu App Secret: ").strip()

    if not app_secret:
        return {}

    # Connection mode
    print("\nConnection mode:")
    print("  1. WebSocket (Long Connection) — recommended, no public URL needed")
    print("  2. Webhook (HTTP) — requires a public HTTPS URL")
    mode_choice = input("Choose mode [1]: ").strip()
    use_websocket = mode_choice != "2"

    webhook_path = ""
    if not use_websocket:
        webhook_path = input("Webhook path (default: /feishu/event): ").strip() or "/feishu/event"

    # DM policy
    print("\nDM Policy (who can message your bot):")
    print("  1. Open - Allow all users")
    print("  2. Pairing - Require approval (recommended)")
    dm_policy = "open" if input("Choose DM policy [2]: ").strip() == "1" else "pairing"

    config: dict = {
        "enabled": True,
        "appId": app_id,
        "appSecret": app_secret,
        "useWebSocket": use_websocket,
        "dmPolicy": dm_policy,
    }
    if not use_websocket and webhook_path:
        config["webhookPath"] = webhook_path

    return config


def configure_whatsapp_enhanced() -> dict:
    """Configure WhatsApp via Baileys bridge (QR-code pairing, no API key required)."""
    print("\nWhatsApp uses a local Baileys bridge (Node.js) for connectivity.")
    print("You will scan a QR code to link your WhatsApp account on first start.\n")

    # Account name / identifier
    account_name = input("Account name / identifier (e.g. 'personal', default: 'default'): ").strip() or "default"

    # DM policy
    print("\nDM Policy:")
    print("  1. Open - Accept messages from any number")
    print("  2. Pairing - Require approval (recommended)")
    print("  3. Allowlist - Specific numbers only (E.164 format, e.g. +1234567890)")
    policy_choice = input("Choose DM policy [2]: ").strip()
    if policy_choice == "1":
        dm_policy = "open"
    elif policy_choice == "3":
        dm_policy = "allowlist"
    else:
        dm_policy = "pairing"

    config: dict = {
        "enabled": True,
        "accounts": {
            account_name: {
                "enabled": True,
                "dmPolicy": dm_policy,
                "groupPolicy": "allowlist",
            }
        },
    }

    if dm_policy == "allowlist":
        raw = input("Allowed phone numbers (E.164, comma-separated, e.g. +1234567890): ").strip()
        if raw:
            numbers = [n.strip() for n in raw.split(",") if n.strip()]
            config["accounts"][account_name]["allowFrom"] = numbers

    return config


async def configure_channels() -> dict:
    """Configure chat channels.
    
    Returns:
        Channel configuration
    """
    print("\n" + "=" * 60)
    print("Channel Configuration")
    print("=" * 60)
    print("\nWhich messaging channels would you like to configure?")
    print("(You can add more later with: openclaw channels add)\n")
    
    channels = {}
    
    # Telegram
    setup_telegram = input("Configure Telegram? [Y/n]: ").strip().lower()
    if setup_telegram != "n":
        tg_config = configure_telegram_enhanced()
        if tg_config:
            channels["telegram"] = tg_config
            print("✓ Telegram configured\n")
    
    # Discord
    setup_discord = input("Configure Discord? [y/N]: ").strip().lower()
    if setup_discord == "y":
        dc_config = configure_discord_enhanced()
        if dc_config:
            channels["discord"] = dc_config
            print("✓ Discord configured\n")
    
    # Feishu / Lark
    setup_feishu = input("Configure Feishu / Lark? [y/N]: ").strip().lower()
    if setup_feishu == "y":
        fs_config = configure_feishu_enhanced()
        if fs_config:
            channels["feishu"] = fs_config
            print("✓ Feishu / Lark configured\n")
    
    # WhatsApp
    setup_whatsapp = input("Configure WhatsApp? [y/N]: ").strip().lower()
    if setup_whatsapp == "y":
        wa_config = configure_whatsapp_enhanced()
        if wa_config:
            channels["whatsapp"] = wa_config
            print("✓ WhatsApp configured\n")

    # Slack
    setup_slack = input("Configure Slack? [y/N]: ").strip().lower()
    if setup_slack == "y":
        env_token = os.getenv("SLACK_BOT_TOKEN")
        token = env_token if env_token else input("Slack bot token: ").strip()
        if token:
            channels["slack"] = {
                "enabled": True,
                "bot_token": token,
                "dm_policy": "pairing",
            }
            print("✓ Slack configured\n")
    
    return channels
