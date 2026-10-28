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


def _words_deep(command: str, depth: int = 0) -> List[str]:
    """Every word in a command line, and every word inside its quoted strings, split on `=` too.

    A quoted string can be a command in waiting (`bash -lc '…'`, `bash <<<'…'`, `echo '…' | sh`,
    `git -c core.sshCommand='ssh …'`), so its words are checked like the outer ones.
    """
    tokens = shellwords.tokenize(command)
    if tokens is None:
        tokens = command.split()
    words = []
    for token in tokens:
        if shellwords.is_operator(token):
            continue
        words.append(token)
        words.extend(part for part in token.split("=")[1:] if part)
        if depth < 3 and (" " in token or "=" in token or ";" in token):
            for inner in [token] + token.split("=")[1:]:
                if inner != token or " " in token or ";" in token:
                    words.extend(_words_deep(inner, depth + 1))
    return words


def names_a_secret(token: str) -> bool:
    """Does this word name (or glob-match) the drop box, the secrets store or the studio's SSH key?"""
    lowered = token.lower().replace("\\", "/")
    if any(mark in lowered for mark in ("credentials.txt", "controlpath")):
        return True
    parts = [part for part in lowered.split("/") if part not in ("", ".")]
    for index, part in enumerate(parts):
        if fnmatch.fnmatchcase("credentials.txt", part):
            return True
        if fnmatch.fnmatchcase("wp-studio", part) or fnmatch.fnmatchcase("wpstudio_ed25519", part) \
                or fnmatch.fnmatchcase("wpstudio_ed25519.pub", part):
            return True
        if part == "wpstudio" and index > 0 and parts[index - 1] == ".ssh":
            return True
        if fnmatch.fnmatchcase(".config", part) and index == len(parts) - 1:
            return True  # the folder that holds the secrets store, searched as a whole
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


def _remote_violation(command: str) -> bool:
    """Fail closed: any ssh-family program named anywhere, in any quoted string, is refused."""
    for word in _words_deep(command):
        base = word.rsplit("/", 1)[-1]
        if base in REMOTE_TOOLS:
            return True
    tokens = shellwords.tokenize(command)
    for program, args in (_commands(tokens) if tokens is not None else []):
        if program.rsplit("/", 1)[-1] == "rsync" and any(
                a in ("-e", "--rsh") or a.startswith("--rsh=") or a.startswith("rsync://")
                or (":" in a and not a.startswith(("/", "./", "../", "~")) and "://" not in a) for a in args):
            return True
    return False


def _agent_violation(command: str) -> Optional[str]:
    """Read-only agents may only run wpsite commands that can't change a site, at the top level."""
    tokens = shellwords.tokenize(command)
    if tokens is None:
        return "Blocked: this agent is read-only and that command couldn't be checked."
    mentions = sum(1 for w in _words_deep(command) if "wpsite" in w)
    checked = 0
    for program, args in _commands(tokens):
        if program != "wpsite":
            continue
        checked += 1
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
    if mentions > checked:
        return "Blocked: this agent is read-only; run wpsite commands directly, not through another program or path."
    return None


def check_bash(command: str, agent_type: Optional[str] = None) -> Optional[dict]:
    """Return a deny decision for a Bash command, or None to let it through."""
    if any(names_a_secret(w) for w in _words_deep(command)):
        return _deny(SECRET_REASON)
    if CURL_REMOTE_FILE.search(command) or _remote_violation(command):
        return _deny(REMOTE_REASON)
    if agent_type and agent_type.split(":")[-1] in READ_ONLY_AGENTS:
        reason = _agent_violation(command)
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
