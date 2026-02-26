#!/usr/bin/env python3
"""Compare two .openclaw folders and generate a detailed diff report.

Usage:
    python scripts/compare_dotopenclaw.py <ts_openclaw_dir> <py_openclaw_dir>
    
Example:
    python scripts/compare_dotopenclaw.py ~/tsdotopenclaw ~/pydotopenclaw
"""
import json
import sys
from pathlib import Path
from typing import Any


def compare_folders(ts_dir: Path, py_dir: Path) -> dict[str, Any]:
    """Compare two .openclaw folders and return differences.
    
    Args:
        ts_dir: TypeScript .openclaw directory
        py_dir: Python .openclaw directory
        
    Returns:
        Dict with comparison results
    """
    results = {
        "missing_in_python": [],
        "extra_in_python": [],
        "json_field_diffs": [],
        "file_count_ts": 0,
        "file_count_py": 0,
        "folder_count_ts": 0,
        "folder_count_py": 0,
    }
    
    # Get all files and folders
    ts_files = set()
    ts_folders = set()
    
    for item in ts_dir.rglob("*"):
        rel_path = item.relative_to(ts_dir)
        if item.is_file():
            ts_files.add(str(rel_path))
        elif item.is_dir():
            ts_folders.add(str(rel_path))
    
    py_files = set()
    py_folders = set()
    
    for item in py_dir.rglob("*"):
        rel_path = item.relative_to(py_dir)
        if item.is_file():
            py_files.add(str(rel_path))
        elif item.is_dir():
            py_folders.add(str(rel_path))
    
    results["file_count_ts"] = len(ts_files)
    results["file_count_py"] = len(py_files)
    results["folder_count_ts"] = len(ts_folders)
    results["folder_count_py"] = len(py_folders)
    
    # Find missing folders
    missing_folders = ts_folders - py_folders
    for folder in sorted(missing_folders):
        results["missing_in_python"].append({"type": "folder", "path": folder})
    
    # Find extra folders
    extra_folders = py_folders - ts_folders
    for folder in sorted(extra_folders):
        results["extra_in_python"].append({"type": "folder", "path": folder})
    
    # Find missing files
    missing_files = ts_files - py_files
    for file in sorted(missing_files):
        results["missing_in_python"].append({"type": "file", "path": file})
    
    # Find extra files
    extra_files = py_files - ts_files
    for file in sorted(extra_files):
        results["extra_in_python"].append({"type": "file", "path": file})
    
    # Compare JSON files that exist in both
    common_files = ts_files & py_files
    json_files = [f for f in common_files if f.endswith(".json")]
    
    for json_file in sorted(json_files):
        ts_path = ts_dir / json_file
        py_path = py_dir / json_file
        
        try:
            ts_data = json.loads(ts_path.read_text(encoding="utf-8"))
            py_data = json.loads(py_path.read_text(encoding="utf-8"))
            
            diff = compare_json_structure(ts_data, py_data, json_file)
            if diff:
                results["json_field_diffs"].append({
                    "file": json_file,
                    "differences": diff
                })
        except Exception as e:
            results["json_field_diffs"].append({
                "file": json_file,
                "error": str(e)
            })
    
    return results


def compare_json_structure(ts_data: Any, py_data: Any, path: str = "") -> list[str]:
    """Recursively compare JSON structures and find differences.
    
    Args:
        ts_data: TypeScript data
        py_data: Python data
        path: Current path for error reporting
        
    Returns:
        List of difference descriptions
    """
    diffs = []
    
    if type(ts_data) != type(py_data):
        diffs.append(f"{path}: Type mismatch (TS: {type(ts_data).__name__}, Py: {type(py_data).__name__})")
        return diffs
    
    if isinstance(ts_data, dict):
        # Check for missing keys in Python
        ts_keys = set(ts_data.keys())
        py_keys = set(py_data.keys())
        
        missing_keys = ts_keys - py_keys
        for key in sorted(missing_keys):
            diffs.append(f"{path}.{key}: Missing in Python")
        
        extra_keys = py_keys - ts_keys
        for key in sorted(extra_keys):
            diffs.append(f"{path}.{key}: Extra in Python")
        
        # Compare common keys recursively
        common_keys = ts_keys & py_keys
        for key in sorted(common_keys):
            new_path = f"{path}.{key}" if path else key
            diffs.extend(compare_json_structure(ts_data[key], py_data[key], new_path))
    
    elif isinstance(ts_data, list):
        if len(ts_data) != len(py_data):
            diffs.append(f"{path}: Array length mismatch (TS: {len(ts_data)}, Py: {len(py_data)})")
        # Note: We don't recursively compare array items to avoid noise
    
    return diffs


def print_report(results: dict[str, Any]) -> None:
    """Print a formatted comparison report.
    
    Args:
        results: Comparison results from compare_folders()
    """
    print("\n" + "=" * 80)
    print("📊 .OPENCLAW FOLDER COMPARISON REPORT")
    print("=" * 80)
    
    print(f"\n📈 Summary:")
    print(f"  TS Files:    {results['file_count_ts']}")
    print(f"  Py Files:    {results['file_count_py']}")
    print(f"  TS Folders:  {results['folder_count_ts']}")
    print(f"  Py Folders:  {results['folder_count_py']}")
    
    # Missing in Python
    missing = results["missing_in_python"]
    if missing:
        print(f"\n❌ Missing in Python ({len(missing)} items):")
        for item in missing:
            icon = "📁" if item["type"] == "folder" else "📄"
            print(f"  {icon} {item['path']}")
    else:
        print(f"\n✅ No missing files or folders in Python")
    
    # Extra in Python
    extra = results["extra_in_python"]
    if extra:
        print(f"\n➕ Extra in Python ({len(extra)} items):")
        for item in extra:
            icon = "📁" if item["type"] == "folder" else "📄"
            print(f"  {icon} {item['path']}")
    else:
        print(f"\n✅ No extra files or folders in Python")
    
    # JSON field differences
    json_diffs = results["json_field_diffs"]
    if json_diffs:
        print(f"\n🔍 JSON Field Differences ({len(json_diffs)} files):")
        for diff in json_diffs:
            print(f"\n  📄 {diff['file']}:")
            if "error" in diff:
                print(f"    ⚠️  Error: {diff['error']}")
            else:
                for d in diff["differences"]:
                    print(f"    • {d}")
    else:
        print(f"\n✅ All JSON files have matching structure")
    
    # Overall verdict
    print("\n" + "=" * 80)
    if not missing and not extra and not json_diffs:
        print("🎉 SUCCESS: Python .openclaw fully aligned with TypeScript!")
    else:
        print("⚠️  ALIGNMENT INCOMPLETE: See differences above")
    print("=" * 80 + "\n")


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    
    ts_dir = Path(sys.argv[1]).expanduser().resolve()
    py_dir = Path(sys.argv[2]).expanduser().resolve()
    
    if not ts_dir.exists():
        print(f"❌ Error: TS directory not found: {ts_dir}")
        sys.exit(1)
    
    if not py_dir.exists():
        print(f"❌ Error: Python directory not found: {py_dir}")
        sys.exit(1)
    
    print(f"🔍 Comparing directories:")
    print(f"  TS: {ts_dir}")
    print(f"  Py: {py_dir}")
    
    results = compare_folders(ts_dir, py_dir)
    print_report(results)
    
    # Exit with error code if differences found
    has_diffs = (
        results["missing_in_python"] or 
        results["extra_in_python"] or 
        results["json_field_diffs"]
    )
    sys.exit(1 if has_diffs else 0)


if __name__ == "__main__":
    main()
