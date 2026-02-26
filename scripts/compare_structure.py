#!/usr/bin/env python3
"""Compare Python and TypeScript openclaw directory structures."""
import json
from pathlib import Path
from typing import Set

# Directories to compare
TS_DIR = Path("/Users/long/Desktop/XJarvis/tsdotopenclaw")
PY_TEST_ROOT = Path.home() / ".openclaw"

def get_directory_structure(base_dir: Path, exclude_patterns: Set[str] = None) -> dict:
    """Get directory structure recursively."""
    if exclude_patterns is None:
        exclude_patterns = {'.git', '__pycache__', 'node_modules', '.DS_Store', 'devices'}
    
    structure = {
        "directories": set(),
        "files": set(),
    }
    
    if not base_dir.exists():
        return structure
    
    for item in base_dir.rglob("*"):
        # Skip excluded patterns
        if any(pattern in str(item) for pattern in exclude_patterns):
            continue
        
        relative = item.relative_to(base_dir)
        
        if item.is_dir():
            structure["directories"].add(str(relative))
        elif item.is_file():
            structure["files"].add(str(relative))
    
    return structure


def compare_required_directories(ts_dir: Path, py_dir: Path) -> dict:
    """Compare required top-level directories between TS and Python versions."""
    
    # Required directories from TS version
    required_dirs = [
        "identity",
        "delivery-queue", 
        "completions",
        "canvas",
        "logs",
        "workspace",
    ]
    
    # Required files
    required_files = {
        "identity/device.json",
        "identity/device-auth.json",
        "canvas/index.html",
        "logs/gateway.log",
        "logs/gateway.err.log",
        "logs/config-audit.jsonl",
        "completions/openclaw.bash",
        "completions/openclaw.zsh",
        "completions/openclaw.fish",
        "completions/openclaw.ps1",
    }
    
    result = {
        "directories": {
            "ts_present": [],
            "py_present": [],
            "missing_in_py": [],
            "match": True
        },
        "files": {
            "ts_present": [],
            "py_present": [],
            "missing_in_py": [],
            "match": True
        }
    }
    
    # Check directories
    for dir_name in required_dirs:
        ts_path = ts_dir / dir_name
        py_path = py_dir / dir_name
        
        if ts_path.exists() and ts_path.is_dir():
            result["directories"]["ts_present"].append(dir_name)
        
        if py_path.exists() and py_path.is_dir():
            result["directories"]["py_present"].append(dir_name)
        else:
            result["directories"]["missing_in_py"].append(dir_name)
            result["directories"]["match"] = False
    
    # Check required files
    for file_path in required_files:
        ts_path = ts_dir / file_path
        py_path = py_dir / file_path
        
        if ts_path.exists() and ts_path.is_file():
            result["files"]["ts_present"].append(file_path)
        
        if py_path.exists() and py_path.is_file():
            result["files"]["py_present"].append(file_path)
        else:
            result["files"]["missing_in_py"].append(file_path)
            result["files"]["match"] = False
    
    return result


def main():
    print("=" * 80)
    print("OpenClaw Directory Structure Comparison")
    print("=" * 80)
    print(f"\nTypeScript version: {TS_DIR}")
    print(f"Python version:     {PY_TEST_ROOT}")
    print()
    
    # Check if directories exist
    if not TS_DIR.exists():
        print(f"❌ TypeScript directory not found: {TS_DIR}")
        return
    
    if not PY_TEST_ROOT.exists():
        print(f"⚠️  Python directory not found: {PY_TEST_ROOT}")
        print("   This is normal if onboarding hasn't been run yet.")
        print("   The directories will be created during first run.")
        return
    
    # Compare structures
    comparison = compare_required_directories(TS_DIR, PY_TEST_ROOT)
    
    # Print results
    print("\n" + "=" * 80)
    print("Directory Comparison")
    print("=" * 80)
    
    if comparison["directories"]["match"]:
        print("✅ All required directories present in Python version")
        for dir_name in sorted(comparison["directories"]["py_present"]):
            print(f"   ✓ {dir_name}/")
    else:
        print("⚠️  Some directories missing in Python version:")
        for dir_name in sorted(comparison["directories"]["missing_in_py"]):
            print(f"   ✗ {dir_name}/")
        
        if comparison["directories"]["py_present"]:
            print("\n   Present:")
            for dir_name in sorted(comparison["directories"]["py_present"]):
                print(f"   ✓ {dir_name}/")
    
    print("\n" + "=" * 80)
    print("File Comparison")
    print("=" * 80)
    
    if comparison["files"]["match"]:
        print("✅ All required files present in Python version")
        for file_path in sorted(comparison["files"]["py_present"]):
            print(f"   ✓ {file_path}")
    else:
        print("⚠️  Some files missing in Python version:")
        for file_path in sorted(comparison["files"]["missing_in_py"]):
            print(f"   ✗ {file_path}")
        
        if comparison["files"]["py_present"]:
            print("\n   Present:")
            for file_path in sorted(comparison["files"]["py_present"]):
                print(f"   ✓ {file_path}")
    
    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    
    total_dirs = len(comparison["directories"]["ts_present"])
    present_dirs = len(comparison["directories"]["py_present"])
    total_files = len(comparison["files"]["ts_present"])
    present_files = len(comparison["files"]["py_present"])
    
    print(f"Directories: {present_dirs}/{total_dirs} present")
    print(f"Files:       {present_files}/{total_files} present")
    
    if comparison["directories"]["match"] and comparison["files"]["match"]:
        print("\n✅ Python version matches TypeScript version structure!")
    else:
        print("\n⚠️  Python version is missing some components")
        print("   Run onboarding to create missing directories: uv run openclaw onboard")


if __name__ == "__main__":
    main()
