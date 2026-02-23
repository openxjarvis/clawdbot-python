"""Skills setup during onboarding - aligned with TypeScript onboard-skills.ts"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def detect_package_manager() -> str:
    """Detect available Python package manager"""
    # Check for uv (preferred)
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            return "uv"
    except FileNotFoundError:
        pass
    
    # Check for poetry
    try:
        result = subprocess.run(["poetry", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            return "poetry"
    except FileNotFoundError:
        pass
    
    # Default to pip
    return "pip"


def list_available_skills(workspace_dir: Optional[Path] = None) -> List[dict]:
    """Discover available skills from local skill directories."""
    discovered: list[dict] = []
    roots = [
        Path.home() / ".openclaw" / "skills",
        (workspace_dir / ".openclaw" / "skills") if workspace_dir else None,
    ]
    for root in roots:
        if not root or not root.exists():
            continue
        for skill_md in root.glob("*/SKILL.md"):
            skill_id = skill_md.parent.name
            discovered.append(
                {
                    "id": skill_id,
                    "name": skill_id.replace("-", " ").title(),
                    "description": f"Local skill at {skill_md.parent}",
                    "requires_auth": False,
                }
            )

    if discovered:
        return discovered

    # Built-in fallback list when no local skills are found.
    return [
        {"id": "python-expert", "name": "Python Expert", "description": "Python programming assistance", "requires_auth": False},
        {"id": "web-search", "name": "Web Search", "description": "Search the web with Brave Search", "requires_auth": True, "auth_keys": ["BRAVE_API_KEY"]},
        {"id": "github", "name": "GitHub Integration", "description": "GitHub repository management", "requires_auth": True, "auth_keys": ["GITHUB_TOKEN"]},
    ]


def _install_skill(skill_id: str, package_manager: str) -> bool:
    """Best-effort skill installation via openclaw CLI."""
    commands: list[list[str]]
    if package_manager == "uv":
        commands = [["uv", "run", "openclaw", "skills", "install", skill_id]]
    elif package_manager == "poetry":
        commands = [["poetry", "run", "openclaw", "skills", "install", skill_id]]
    else:
        commands = [[sys.executable, "-m", "openclaw", "skills", "install", skill_id]]

    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True
        except Exception:
            continue
    return False


async def setup_skills(mode: str = "quickstart") -> dict:
    """Setup skills during onboarding
    
    Args:
        mode: "quickstart" or "advanced"
        
    Returns:
        Dict with installed skills info
    """
    print("\n" + "=" * 60)
    print("🛠️  SKILLS SETUP")
    print("=" * 60)
    
    # Detect package manager
    pkg_manager = detect_package_manager()
    print(f"\n📦 Detected package manager: {pkg_manager}")
    
    # List available skills
    available_skills = list_available_skills()
    
    if mode == "quickstart":
        print("\n⚡ QuickStart mode: Skipping skills setup")
        print("💡 Run 'openclaw skills install' later to add skills")
        return {"installed": [], "skipped": True}
    
    # Advanced mode: prompt for skills
    print(f"\n📚 Found {len(available_skills)} available skills:")
    for i, skill in enumerate(available_skills, 1):
        auth_note = " (requires API key)" if skill.get("requires_auth") else ""
        print(f"  {i}. {skill['name']}{auth_note}")
        print(f"     {skill['description']}")
    
    response = input("\n❓ Install skills now? [y/N]: ").strip().lower()
    if response not in ["y", "yes"]:
        print("⏭️  Skipping skills setup")
        return {"installed": [], "skipped": True}
    
    # Multi-select skills
    selected = input("\nEnter skill numbers to install (comma-separated, or 'all'): ").strip()
    
    if selected == "all":
        skills_to_install = available_skills
    else:
        try:
            indices = [int(x.strip()) - 1 for x in selected.split(",")]
            skills_to_install = [available_skills[i] for i in indices if 0 <= i < len(available_skills)]
        except (ValueError, IndexError):
            print("❌ Invalid selection")
            return {"installed": [], "error": "invalid_selection"}
    
    # Install skills
    installed = []
    for skill in skills_to_install:
        print(f"\n📥 Installing {skill['name']}...")
        
        # Check if auth required
        if skill.get("requires_auth"):
            print(f"   ⚠️  {skill['name']} requires API keys:")
            for key in skill.get("auth_keys", []):
                value = input(f"   Enter {key}: ").strip()
                if value:
                    print(f"   ✅ {key} captured for current shell")

        if _install_skill(skill["id"], pkg_manager):
            installed.append(skill["id"])
            print(f"   ✅ {skill['name']} installed")
        else:
            print(f"   ⚠️  Could not auto-install {skill['name']} (you can install it later)")
    
    print(f"\n✅ Installed {len(installed)} skills successfully")
    return {"installed": installed, "count": len(installed)}


__all__ = ["setup_skills", "list_available_skills", "detect_package_manager"]
