"""Find the studio workspace and the paths inside it.

A workspace is the operator's studio folder. It is marked by a `.wp-studio` file at its root, so
the plugin never acts on a folder that isn't a studio, even if it is enabled there by mistake.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Optional

MARKER = ".wp-studio"
DROPBOX = "CREDENTIALS.txt"


class NotAWorkspace(Exception):
    """Raised when a command needs a studio workspace and none encloses the current folder."""


def find_root(start: Optional[Path] = None) -> Optional[Path]:
    """Return the nearest enclosing workspace root, or None.

    Search order: CLAUDE_PROJECT_DIR (set for hooks), then the given folder or the current one,
    walking up to the filesystem root.
    """
    candidates = []
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        candidates.append(Path(env))
    candidates.append(start or Path.cwd())
    for base in candidates:
        base = base.resolve()
        for folder in (base, *base.parents):
            if (folder / MARKER).is_file():
                return folder
    return None


def require_root(start: Optional[Path] = None) -> Path:
    root = find_root(start)
    if root is None:
        raise NotAWorkspace(
            "This isn't inside a Claude WP Studio folder (no .wp-studio file found). "
            "Run this from your studio folder."
        )
    return root


def projects_dir(root: Path) -> Path:
    return root / "projects"


def clients_dir(root: Path) -> Path:
    return root / "clients"


def dropbox_path(root: Path) -> Path:
    return root / DROPBOX


def studio_id(root: Path) -> str:
    """The studio's stable ID, kept in its .wp-studio marker (created on first use)."""
    marker = root / MARKER
    text = marker.read_text(encoding="utf-8") if marker.is_file() else ""
    match = re.search(r"^id=([0-9a-f-]{36})$", text, re.M)
    if match:
        return match.group(1)
    new = str(uuid.uuid4())
    marker.write_text(text.rstrip("\n") + ("\n" if text.strip() else "") + "id=%s\n" % new, encoding="utf-8")
    return new


def secrets_home() -> Path:
    """Where every studio keeps site connection details: outside any studio folder, so nothing Claude
    runs inside the studio (a recursive grep, a script) can come across them."""
    return Path(os.environ.get("WPSTUDIO_SECRETS_HOME", str(Path.home() / ".config" / "wp-studio" / "secrets")))


def secrets_dir(root: Path) -> Path:
    path = secrets_home() / studio_id(root)
    path.mkdir(parents=True, exist_ok=True)
    for folder in (secrets_home().parent, secrets_home(), path):
        if folder.is_dir():
            os.chmod(folder, 0o700)
    return path
