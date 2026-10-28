"""Save the studio: commit locally (after the secret scan) and push to the operator's backup.

The push runs in a detached process. Claude Code gives SessionEnd hooks a short time budget, and a
push over a slow connection can outlast it; a detached push finishes on its own and records its
result in .git/wp-studio-push.json, which the next session reports if it failed.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from . import PLUGIN_ROOT, scan

STATUS = "wp-studio-push.json"


def git(root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, text=True, check=check)


def git_dir(root: Path) -> Path:
    return Path(git(root, "rev-parse", "--absolute-git-dir", check=True).stdout.strip())


def ensure_repo(root: Path) -> None:
    # The studio is its own repository, even inside another one: never commit a parent repo's files.
    top = git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != root.resolve():
        git(root, "init", "-b", "main", check=True)
    if not git(root, "config", "user.email").stdout.strip():
        git(root, "config", "user.email", "wp-studio@localhost")
    if not git(root, "config", "user.name").stdout.strip():
        git(root, "config", "user.name", "Claude WP Studio")


def commit(root: Path, message: Optional[str]) -> int:
    """Stage everything, scan, commit. Returns 0 (saved or nothing to save) or 1 (refused)."""
    ensure_repo(root)
    git(root, "add", "-A", check=True)
    if git(root, "diff", "--cached", "--quiet").returncode == 0:
        return 0
    findings = scan.scan_staged(root)
    if findings:
        git(root, "reset", "-q")
        print("Not saved: these would put a secret or a site's private data into the backup:")
        for finding in findings:
            print("  " + str(finding))
        print("Take the secret out of that file (site logins belong only in the drop box, filed with "
              "`wpsite secrets file`), then save again.")
        return 1
    message = message or "Studio update %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    result = git(root, "commit", "-q", "-m", message)
    if result.returncode != 0:
        print("Not saved: git commit failed: %s" % (result.stderr.strip() or result.stdout.strip()))
        return 1
    print("Saved: %s" % message)
    return 0


def has_remote(root: Path) -> bool:
    return git(root, "remote", "get-url", "origin").returncode == 0


def push_now(root: Path) -> int:
    """Push and record the outcome. Runs in the foreground (used by the detached child)."""
    started = time.time()
    result = git(root, "push", "-q", "origin", "HEAD")
    status = {
        "time": dt.datetime.now().isoformat(timespec="seconds"),
        "ok": result.returncode == 0,
        "seconds": round(time.time() - started, 1),
        "message": (result.stderr or result.stdout).strip()[-500:],
    }
    (git_dir(root) / STATUS).write_text(json.dumps(status, indent=2), encoding="utf-8")
    return 0 if status["ok"] else 1


def push_detached(root: Path) -> None:
    log = open(git_dir(root) / "wp-studio-push.log", "ab")
    subprocess.Popen(
        [sys.executable, str(PLUGIN_ROOT / "bin" / "studio"), "push-now"],
        cwd=str(root), stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)),
    )


def last_push(root: Path) -> Optional[dict]:
    try:
        return json.loads((git_dir(root) / STATUS).read_text(encoding="utf-8"))
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def save(root: Path, message: Optional[str], detach: bool) -> int:
    code = commit(root, message)
    if code != 0:
        return code
    if not has_remote(root):
        print("Saved locally (no GitHub backup linked).")
        return 0
    if detach:
        push_detached(root)
        print("Backing up to GitHub in the background.")
        return 0
    if push_now(root) == 0:
        print("Backed up to GitHub.")
        return 0
    status = last_push(root) or {}
    print("Saved locally, but the GitHub backup didn't go through: %s" % status.get("message", "unknown error"))
    return 0
