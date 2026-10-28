"""Keep a workspace's kit-owned files in step with the installed plugin, and migrate v1 studios.

Two kinds of file in a workspace:
- Kit-owned: the plugin ships them and rewrites them whenever they differ (settings, the operating
  manual, the launcher, .gitignore, the pre-commit hook). Operators customize through
  CLAUDE.md and .claude/settings.local.json instead, which the kit never touches.
- Operator-owned: created once from a template if missing, then never touched.

This is how a plugin update reaches the workspace: the plugin updates in the background, and the
next session start brings the workspace's kit-owned files up to date.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path
from typing import List

from . import PLUGIN_ROOT, __version__, dropbox, workspace

TEMPLATES = PLUGIN_ROOT / "templates" / "workspace"

# workspace path -> template path (relative to TEMPLATES)
KIT_OWNED = {
    ".claude/settings.json": "settings.json",
    ".claude/launch-settings.json": "launch-settings.json",
    ".claude/studio-manual.md": "studio-manual.md",
    ".gitignore": "gitignore",
    "studio.sh": "studio.sh",
}
EXECUTABLE = {"studio.sh"}
OPERATOR_OWNED = {
    "CLAUDE.md": "CLAUDE.md",
    "WORKLOG.md": "WORKLOG.md",
    "clients/README.md": "clients-README.md",
    "projects/.gitkeep": None,
}

PRE_COMMIT = """#!/bin/sh
# Installed by Claude WP Studio (rewritten each session): refuse a commit that contains a secret.
STUDIO="{studio}"
if [ ! -f "$STUDIO" ]; then
  echo "The studio's secret check is missing. Open the studio (./studio.sh) once to repair it, then commit again." >&2
  exit 1
fi
exec "{python}" "$STUDIO" scan --staged
"""


def _write_if_changed(path: Path, content: bytes, executable: bool = False) -> bool:
    if path.is_file() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".wpstudio-tmp")
    tmp.write_bytes(content)
    if executable:
        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(tmp, path)
    return True


def pre_commit_hook() -> bytes:
    return PRE_COMMIT.format(python=sys.executable, studio=PLUGIN_ROOT / "bin" / "studio").encode("utf-8")


def sync(root: Path) -> List[str]:
    """Bring kit-owned files up to date; create missing operator files. Returns what changed."""
    changed = []
    for rel, template in KIT_OWNED.items():
        if _write_if_changed(root / rel, (TEMPLATES / template).read_bytes(), executable=rel in EXECUTABLE):
            changed.append(rel)
    for rel, template in OPERATOR_OWNED.items():
        target = root / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((TEMPLATES / template).read_bytes() if template else b"")
        changed.append(rel)
    box = workspace.dropbox_path(root)
    if not box.exists():
        dropbox.wipe(box)
        changed.append(box.name)
    git_dir = root / ".git"
    if git_dir.is_dir():
        if _write_if_changed(git_dir / "hooks" / "pre-commit", pre_commit_hook(), executable=True):
            changed.append(".git/hooks/pre-commit")
    marker = root / workspace.MARKER
    stamp = ("Claude WP Studio workspace. Kit version %s.\n" % __version__).encode("utf-8")
    if _write_if_changed(marker, stamp):
        changed.append(workspace.MARKER)
    return changed


# ── v1 → v2 ─────────────────────────────────────────────────────────────────────────────────────

V1_SIGNS = ("tooling/catalog.py", "library/INDEX.md", "START_HERE.md")
V1_KIT_PATHS = (
    "START_HERE.md", "GETTING_STARTED.md", "SECURITY.md", "README.md", "LICENSE", "install.sh", ".mcp.json",
    "CREDENTIALS.txt.template", "guides", "tooling", "library/lessons", "library/playbooks", "library/reference",
    "library/INDEX.md", "library/CONTRIBUTING.md", "library/catalog.db", "library/clients/README.md",
)


def is_v1(root: Path) -> bool:
    return any((root / sign).exists() for sign in V1_SIGNS) and not (root / workspace.MARKER).exists()


def migrate_v1(root: Path) -> List[str]:
    """Turn a v1 studio folder into a v2 workspace in place. Nothing of the operator's is deleted:
    client docs move to clients/, the old manual is kept as CLAUDE.v1.md, and v1 connection files are
    renamed to the v2 name. Everything is in git history as well."""
    notes = []
    old_clients = root / "library" / "clients"
    if old_clients.is_dir():
        (root / "clients").mkdir(exist_ok=True)
        for doc in old_clients.glob("*.md"):
            if doc.name == "README.md":
                continue
            target = root / "clients" / doc.name
            if not target.exists():
                shutil.move(str(doc), str(target))
                notes.append("moved library/clients/%s to clients/" % doc.name)
    for project in (root / "projects").glob("*"):
        old_env = project / ".secrets" / "connection.env"
        if old_env.is_file() and not (project / ".secrets" / "live.env").exists():
            old_env.rename(project / ".secrets" / "live.env")
            notes.append("renamed projects/%s/.secrets/connection.env to live.env" % project.name)
        for helper in ("wp.sh", "db-pull.sh"):
            if (project / helper).is_file():
                (project / helper).unlink()
                notes.append("removed projects/%s/%s (replaced by wpsite)" % (project.name, helper))
        old_backups = project / "backups"
        if old_backups.is_dir() and any(p.is_file() for p in old_backups.iterdir()):
            legacy = old_backups / "v1"
            legacy.mkdir(exist_ok=True)
            for item in old_backups.iterdir():
                if item.is_file():
                    shutil.move(str(item), str(legacy / item.name))
            notes.append("kept projects/%s's old backups under backups/v1/" % project.name)
    manual = root / "CLAUDE.md"
    if manual.is_file():
        manual.rename(root / "CLAUDE.v1.md")
        notes.append("kept the old operating manual as CLAUDE.v1.md (add anything personal from it to CLAUDE.md)")
    for rel in V1_KIT_PATHS:
        path = root / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    library = root / "library"
    for folder in (library / "clients", library):
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    for rel in (".claude/settings.json",):
        (root / rel).unlink() if (root / rel).exists() else None
    sync(root)
    notes.append("installed the v2 workspace files")
    return notes
