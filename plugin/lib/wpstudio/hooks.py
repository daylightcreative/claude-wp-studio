"""The plugin's Claude Code hooks.

- PreToolUse (Bash): keep Claude on the studio's safe routes. Raw ssh/scp/sftp/rsync to a server
  is refused in favour of `wpsite` (which enforces backups, PHP linting and output redaction), and
  any shell command that touches the credential drop box or a site's .secrets/ folder is refused
  unless it is `wpsite` itself. Permission deny rules in the workspace settings cover Claude's file
  tools and the file commands Claude Code recognises; this hook covers the rest of the shell.
- SessionStart: sync kit-owned workspace files, then tell Claude the studio's current state.
- SessionEnd: save (commit locally) and start the backup push in the background.

Every hook does nothing outside a studio workspace.

What the Bash rule can't see: a program that opens a socket or a file by itself (a Python or Node
script written in the session). The auto mode classifier is the layer for that.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, dropbox, save, sync, workspace
from .sites import list_sites

_SEP = r"(?:^|[;&|(\n`]|\$\(|\b(?:sudo|exec|command|env|nohup|time|xargs|then|do|else)\s+|-c\s+[\"'])"
REMOTE_TOOL = re.compile(_SEP + r"\s*(?:[\w./-]*/)?(ssh|scp|sftp|sshpass|ssh-copy-id|lftp|ftp|telnet)(?=\s|$|[;&|)])")
RSYNC_REMOTE = re.compile(_SEP + r"\s*(?:[\w./-]*/)?rsync\b[^;&|\n]*?(?:\s[\w.@-]+:[^\s]*|\s-e\s)")
CURL_REMOTE_FILE = re.compile(r"\b(?:curl|wget)\b[^;&|\n]*\b(?:sftp|scp|ftps?)://", re.I)
SECRET_PATH = re.compile(r"(?:^|[^\w.-])(?:CREDENTIALS\.txt|\.secrets)(?:$|[/\s'\";|&)])")
ONLY_STUDIO_TOOLS = re.compile(r"^\s*(?:wpsite|studio)(?:\s|$)")


def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def _segments(command: str) -> List[str]:
    return [s for s in re.split(r"&&|\|\||[;|\n]", command) if s.strip()]


def check_bash(command: str) -> Optional[dict]:
    """Return a deny decision for a Bash command, or None to let it through."""
    if SECRET_PATH.search(command) and not all(ONLY_STUDIO_TOOLS.match(s) for s in _segments(command)):
        return _deny(
            "Blocked: that command touches the credential drop box or a site's .secrets folder. Claude never reads "
            "those. File what the operator pasted with `wpsite secrets file <site>`, and check what a site has "
            "with `wpsite secrets status <site>` (it lists field names, never values)."
        )
    if REMOTE_TOOL.search(command) or RSYNC_REMOTE.search(command) or CURL_REMOTE_FILE.search(command):
        return _deny(
            "Blocked: connect to sites only through `wpsite` (it backs up before changes, lints PHP before it goes "
            "live, and keeps passwords out of the conversation). Use `wpsite wp <site> …` for WP-CLI, "
            "`wpsite sh <site> '…'` for a shell command, `wpsite deploy` to upload and `wpsite pull` to download."
        )
    return None


def pre_tool_use(event: dict) -> Optional[dict]:
    if event.get("tool_name") != "Bash":
        return None
    command = (event.get("tool_input") or {}).get("command") or ""
    return check_bash(command)


def session_context(root: Path, changed: List[str]) -> str:
    lines = ["Claude WP Studio %s is active in this folder. Reach sites only through `wpsite`." % __version__]
    sites = list_sites(root)
    if sites:
        lines.append("Sites: " + ", ".join(s.spec for s in sites) + ". Details: `wpsite list`.")
    else:
        lines.append("No sites yet. To start one, follow the wp-studio:new-site skill.")
    if dropbox.has_content(workspace.dropbox_path(root)):
        lines.append("The credential drop box has something in it. Ask the operator which site it's for, then run "
                     "`wpsite secrets file <site>`. Don't read CREDENTIALS.txt.")
    status = save.last_push(root)
    if status and not status.get("ok"):
        lines.append("The last GitHub backup push failed (%s): %s. Tell the operator in plain words and offer to "
                     "fix it." % (status.get("time"), status.get("message", "")[:200]))
    kit_changed = [c for c in changed if c in sync.KIT_OWNED]
    if kit_changed:
        lines.append("The studio was updated: refreshed %s. Settings changes apply from the next session."
                     % ", ".join(kit_changed))
    return "\n".join(lines)


def session_start(event: dict) -> Optional[dict]:
    root = workspace.find_root(Path(event.get("cwd") or "."))
    if root is None:
        return None
    changed = sync.sync(root)
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": session_context(root, changed)}}


def session_end(event: dict) -> Optional[dict]:
    root = workspace.find_root(Path(event.get("cwd") or "."))
    if root is None:
        return None
    save.save(root, None, detach=True)
    return None


HANDLERS = {"pre-bash": pre_tool_use, "session-start": session_start, "session-end": session_end}


def run(name: str) -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    if workspace.find_root(Path(event.get("cwd") or ".")) is None:
        return 0
    result = HANDLERS[name](event)
    if result is not None:
        sys.stdout.write(json.dumps(result))
    return 0
