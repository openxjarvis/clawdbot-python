"""pytest conftest: make `src` importable for tests under extensions/feishu/src/."""
import sys
from pathlib import Path

# Add extensions/feishu/ to sys.path so `from src.tools.xxx import ...` resolves.
_PLUGIN_DIR = Path(__file__).parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))
