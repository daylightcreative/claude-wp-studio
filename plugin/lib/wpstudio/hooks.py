"""The plugin's Claude Code hooks.

- PreToolUse (Bash): keep Claude on the studio's safe routes. Raw ssh/scp/sftp/rsync to a server
  is refused in favour of `wpsite` (which enforces backups, PHP linting and output redaction),
  wherever the command sits (after `if`, `sudo`, `env`, inside `sh -c` or `eval`). Any command that
  names the drop box, the secrets store or the studio's SSH key is refused, globs included. Inside
  the read-only agents, `wpsite` commands that can change a site are refused too.
- SessionStart: sync kit-owned workspace files, then tell Claude the studio's current state.
- SessionEnd: save (commit locally) and start the backup push in the background.

Every hook does nothing outside a studio workspace.

What the Bash rule can't see: a program that opens a socket or a file by itself (a Python or Node
script written in the session), a command assembled from variables at run time, or a recursive
search that wanders into a file without naming it. The secrets store sits outside the studio
folder for that reason, and the auto mode classifier reviews the rest.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, dropbox, guard, save, shellwords, sync, workspace
from .sites import list_sites

REMOTE_TOOLS = {"ssh", "scp", "sftp", "sshpass", "ssh-copy-id", "lftp", "ftp", "telnet", "nc", "ncat", "socat"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
# Words after which the next word is still a command: wrappers and shell keywords.
RUNNERS = {"sudo", "env", "exec", "command", "builtin", "nohup", "time", "xargs", "timeout", "nice", "ionice",
           "stdbuf", "caffeinate", "if", "then", "do", "else", "elif", "while", "until", "!", "{", "}"}
CURL_REMOTE_FILE = re.compile(r"\b(?:curl|wget)\b[^;&|\n]*\b(?:sftp|scp|ftps?)://", re.I)
READ_ONLY_AGENTS = {"site-scout", "qa-checker", "page-converter"}

REMOTE_REASON = (
    "Blocked: connect to sites only through `wpsite` (it backs up before changes, lints PHP before it goes "
    "live, and keeps passwords out of the conversation). Use `wpsite wp <site> …` for WP-CLI, "
    "`wpsite sh <site> '…'` for a shell command, `wpsite deploy` to upload and `wpsite pull` to download."
)
SECRET_REASON = (
    "Blocked: that command names the credential drop box, the studio's secrets store or its SSH key. Claude "
    "never reads those. File what the operator pasted with `wpsite secrets file <site>`, and see what a site "
    "has with `wpsite secrets status <site>` (field names only)."
)


def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def names_a_secret(token: str) -> bool:
    """Does this word name (or glob-match) the drop box, the secrets store or the studio's SSH key?"""
    lowered = token.lower()
    if any(mark in lowered for mark in ("credentials.txt", "wp-studio/secrets", "wpstudio_ed25519", ".ssh/wpstudio",
                                        "controlpath")):
        return True
    parts = [p for p in lowered.replace("\\", "/").split("/")]
    for index, part in enumerate(parts):
        if not part:
            continue
        if fnmatch.fnmatchcase("credentials.txt", part):
            return True
        if index > 0 and fnmatch.fnmatchcase("wp-studio", part) and fnmatch.fnmatchcase(".config", parts[index - 1]):
            return True
    return False


def _commands(tokens: List[str]):
    """Yield (program, args) for each command position, unwrapping sudo/env/if/… and `sh -c`."""
    current: List[str] = []
    at_command = True
    for token in tokens + [";"]:
        if shellwords.is_operator(token):
            if current:
                yield current[0], current[1:]
            current, at_command = [], True
            continue
        if at_command and not current:
            base = token.rsplit("/", 1)[-1]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token) or base in RUNNERS:
                continue  # still waiting for the real command
            if token.startswith("-") or token.isdigit():
                continue  # an option or number belonging to the wrapper before it (timeout 5, sudo -u x)
        current.append(token)
    return


def _remote_violation(tokens: List[str], depth: int = 0) -> bool:
    for program, args in _commands(tokens):
        base = program.rsplit("/", 1)[-1]
        if base in REMOTE_TOOLS:
            return True
        if base == "rsync" and any(a in ("-e", "--rsh") or a.startswith("--rsh=")
                                   or (":" in a and not a.startswith(("/", "./", "../", "~")) and "://" not in a)
                                   or a.startswith("rsync://") for a in args):
            return True
        if depth < 3 and base in SHELLS and "-c" in args:
            inner = args[args.index("-c") + 1] if args.index("-c") + 1 < len(args) else ""
            inner_tokens = shellwords.tokenize(inner)
            if inner_tokens is None or _remote_violation(inner_tokens, depth + 1):
                return True
        if depth < 3 and base == "eval":
            inner_tokens = shellwords.tokenize(" ".join(args))
            if inner_tokens is None or _remote_violation(inner_tokens, depth + 1):
                return True
    return False


def _agent_violation(tokens: List[str]) -> Optional[str]:
    """Read-only agents may only run wpsite commands that can't change a site."""
    for program, args in _commands(tokens):
        if program.rsplit("/", 1)[-1] != "wpsite":
            continue
        verb = args[0] if args else ""
        rest = args[1:]
        if verb in ("list", "check", "pull", "backup"):
            continue
        if verb == "secrets" and rest[:1] == ["status"]:
            continue
        if verb == "wp" and len(rest) >= 1 and "--input" not in rest and guard.wp_is_read_only(rest[1:]):
            continue
        if verb == "sh" and len(rest) == 2 and guard.shell_is_read_only(rest[1]):
            continue
        return "Blocked: this agent is read-only and `wpsite %s` can change a site. Report what you'd change instead." % verb
    return None


def check_bash(command: str, agent_type: Optional[str] = None) -> Optional[dict]:
    """Return a deny decision for a Bash command, or None to let it through."""
    tokens = shellwords.tokenize(command)
    words = tokens if tokens is not None else command.split()
    if any(names_a_secret(w) for w in words):
        return _deny(SECRET_REASON)
    if CURL_REMOTE_FILE.search(command) or tokens is None and re.search(r"\b(ssh|scp|sftp|rsync)\b", command):
        return _deny(REMOTE_REASON)
    if tokens is not None and _remote_violation(tokens):
        return _deny(REMOTE_REASON)
    if agent_type and agent_type.split(":")[-1] in READ_ONLY_AGENTS and tokens is not None:
        reason = _agent_violation(tokens)
        if reason:
            return _deny(reason)
    return None


def pre_tool_use(event: dict) -> Optional[dict]:
    if event.get("tool_name") != "Bash":
        return None
    command = (event.get("tool_input") or {}).get("command") or ""
    return check_bash(command, event.get("agent_type"))


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
