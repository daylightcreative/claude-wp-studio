"""Claude WP Studio runtime: the `wpsite` and `studio` commands and the plugin's hooks.

Standard library only, and compatible with the Python 3.9 that ships with Apple's Command Line
Tools, so the studio runs on a Mac with nothing else installed.
"""

import json
from pathlib import Path

# plugin/lib/wpstudio/__init__.py -> plugin/
PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def _version() -> str:
    manifest = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    return json.loads(manifest.read_text(encoding="utf-8"))["version"]


__version__ = _version()
