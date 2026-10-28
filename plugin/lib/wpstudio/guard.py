"""Decide whether a remote command can change a site, and whether a fresh backup covers it.

Rule: anything that can change a site needs a verified database backup of that environment taken
in the last BACKUP_MAX_AGE. The read-only side is an explicit allowlist; everything else counts as
a change. When in doubt it fails closed, so a command this module has never heard of is treated
as a change.
"""

from __future__ import annotations

import json
import re
import shlex
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

BACKUP_MAX_AGE = 2 * 60 * 60  # seconds
BACKUP_GLOB = "db-*.sql.gz"
VERIFIED_SUFFIX = ".verified.json"

# WP-CLI commands that only read, keyed by command path. A value of None means every subcommand
# under that path reads; a set lists the subcommands that read.
_READ_SUB = {
    "list", "get", "status", "exists", "is-installed", "is-active", "path", "search",
    "verify-checksums", "check-update", "version", "count", "pluck", "has", "type",
}
WP_READ = {
    ("core",): {"version", "check-update", "verify-checksums", "is-installed"},
    ("plugin",): _READ_SUB,
    ("theme",): _READ_SUB,
    ("option",): {"get", "list", "pluck"},
    ("post",): {"list", "get", "exists"},
    ("post", "meta"): {"list", "get"},
    ("post", "term"): {"list"},
    ("post-type",): {"list", "get"},
    ("taxonomy",): {"list", "get"},
    ("term",): {"list", "get"},
    ("term", "meta"): {"list", "get"},
    ("user",): {"list", "get", "list-caps", "exists"},
    ("user", "meta"): {"list", "get"},
    ("role",): {"list", "exists"},
    ("cap",): {"list"},
    ("comment",): {"list", "get", "count", "exists"},
    ("comment", "meta"): {"list", "get"},
    ("menu",): {"list"},
    ("menu", "item"): {"list"},
    ("menu", "location"): {"list"},
    ("widget",): {"list"},
    ("sidebar",): {"list"},
    ("db",): {"size", "tables", "columns", "check", "prefix", "search"},
    ("cron", "event"): {"list"},
    ("cron", "schedule"): {"list"},
    ("cron",): {"test"},
    ("cache",): {"get", "type"},
    ("transient",): {"get", "type"},
    ("config",): {"get", "list", "has", "path"},
    ("media",): {"image-size"},
    ("rewrite",): {"list"},
    ("site",): {"list"},
    ("maintenance-mode",): {"status", "is-active"},
    ("language", "core"): {"list"},
    ("language", "plugin"): {"list"},
    ("language", "theme"): {"list"},
    ("cli",): None,
    ("help",): None,
    ("package",): {"list", "path"},
    ("block",): None,
    ("pattern",): {"list", "get"},
}
# Cache clearing changes nothing a backup would restore, so it never needs one.
WP_CACHE_SAFE = {
    ("cache", "flush"), ("kinsta", "cache", "purge"), ("litespeed-purge",), ("rocket", "clean"),
    ("w3-total-cache", "flush"), ("super-cache", "flush"), ("sg", "purge"), ("transient", "delete"),
}
SQL_READ = re.compile(r"^\s*(select|show|describe|desc|explain)\b", re.I)


def wp_command_path(args: Sequence[str]) -> List[str]:
    """The positional words of a WP-CLI invocation, before its first flag-or-value argument."""
    words = []
    for arg in args:
        if arg.startswith("-"):
            continue
        if not re.match(r"^[a-z][a-z0-9-]*$", arg):
            break
        words.append(arg)
    return words


def wp_is_read_only(args: Sequence[str]) -> bool:
    args = [a for a in args if a != "wp"] if args and args[0] == "wp" else list(args)
    if not args or args in (["--info"], ["--version"]):
        return True
    words = wp_command_path(args)
    flags = [a for a in args if a.startswith("--")]
    if not words:
        return all(f in ("--info", "--version") for f in flags)
    for size in (3, 2, 1):
        if tuple(words[:size]) in WP_CACHE_SAFE:
            return True
    if words[0] == "search-replace":
        return "--dry-run" in flags
    if words[:2] == ["db", "query"]:
        positional = [a for a in args[2:] if not a.startswith("-")]
        return len(positional) == 1 and SQL_READ.match(positional[0]) is not None and ";" not in positional[0].rstrip().rstrip(";")
    if words[:2] == ["db", "export"]:
        # `wp db export -` streams to stdout; any file target writes a dump on the server.
        rest = [a for a in args[2:] if not a.startswith("--")]
        return rest == ["-"]
    for size in (2, 1):
        group = tuple(words[:size])
        if group in WP_READ:
            subs = WP_READ[group]
            if subs is None:
                return True
            if len(words) > size and words[size] in subs:
                return True
            if len(words) > size and (group + (words[size],)) in WP_READ:
                continue  # a deeper group decides
            return False
    return False


# Shell programs that only read, for `wpsite sh`. Each entry may forbid flags that make it write.
SHELL_READ = {
    "ls": (), "cat": (), "head": (), "tail": (), "grep": (), "egrep": (), "fgrep": (), "zgrep": (),
    "stat": (), "file": (), "wc": (), "du": (), "df": (), "md5sum": (), "sha1sum": (), "sha256sum": (),
    "pwd": (), "echo": (), "printf": (), "date": (), "whoami": (), "id": (), "uname": (), "hostname": (),
    "test": (), "[": (), "sort": ("-o",), "uniq": (), "cut": (), "tr": (), "zcat": (), "readlink": (),
    "realpath": (), "basename": (), "dirname": (), "tree": (), "strings": (), "od": (), "hexdump": (),
    "ps": (), "uptime": (), "free": (), "nproc": (), "which": (), "command": (), "type": (), "true": (),
    "false": (), "diff": (), "cmp": (), "column": (), "nl": (), "rev": (),
    "find": ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"),
    "sed": ("-i", "--in-place"), "gzip": (), "tar": (), "php": (), "wp": (), "mysql": (), "crontab": (),
}
_SHELL_ONLY_WITH = {
    "gzip": ("-l", "-t", "--list", "--test"),
    "tar": ("-t", "-tf", "-tzf", "-tvf", "-tzvf", "--list"),
    "php": ("-v", "-l", "-m", "-i", "--version", "--ini"),
    "crontab": ("-l",),
}
_SAFE_REDIRECT = re.compile(r"^\d?>{1,2}\s*/dev/null$|^\d?>&\d$|^2>&1$")


def _split_pipeline(command: str) -> Optional[List[List[str]]]:
    """Split a shell command into simple commands. None means "too complex to judge"."""
    if re.search(r"\$\(|`|<<|<\(|>\(", command):
        return None
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    commands: List[List[str]] = [[]]
    pending_redirect: Optional[str] = None
    for token in tokens:
        if pending_redirect is not None:
            if not _SAFE_REDIRECT.match(pending_redirect + token):
                return None
            pending_redirect = None
            continue
        if token in (";", "&&", "||", "|", "&", ";;"):
            commands.append([])
            continue
        if set(token) <= set("<>&") and ">" in token:
            pending_redirect = token
            continue
        if token == "<":
            pending_redirect = None
            continue
        if re.match(r"^\d>$|^\d>>$", token):
            pending_redirect = token
            continue
        commands[-1].append(token)
    if pending_redirect is not None:
        return None
    return [c for c in commands if c]


def shell_is_read_only(command: str) -> bool:
    commands = _split_pipeline(command)
    if commands is None:
        return False
    for words in commands:
        # Leading `cd somewhere` and VAR=value assignments don't write anything.
        while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            words = words[1:]
        if not words:
            continue
        program = words[0].rsplit("/", 1)[-1]
        if program == "cd":
            continue
        if program not in SHELL_READ:
            return False
        args = words[1:]
        if any(a == bad or a.startswith(bad + "=") for a in args for bad in SHELL_READ[program]):
            return False
        if program == "sed" and any(re.search(r"(^|;)\s*w\s", a) for a in args):
            return False
        if program == "wp" and not wp_is_read_only(args):
            return False
        if program == "mysql":
            sql = " ".join(a for a in args if not a.startswith("-"))
            if not SQL_READ.match(sql or ""):
                return False
        if program in _SHELL_ONLY_WITH:
            if not args or not any(a in _SHELL_ONLY_WITH[program] for a in args):
                return False
    return True


def latest_backup(backups: Path) -> Optional[Tuple[Path, float]]:
    """Newest database backup in a folder that `wpsite backup` verified, with its age in seconds."""
    best = None
    for dump in backups.glob(BACKUP_GLOB):
        marker = dump.with_name(dump.name + VERIFIED_SUFFIX)
        if not marker.is_file():
            continue
        try:
            info = json.loads(marker.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if info.get("bytes") != dump.stat().st_size:
            continue  # the dump changed after it was verified
        created = float(info.get("created", 0))
        if best is None or created > best[1]:
            best = (dump, created)
    if best is None:
        return None
    return best[0], max(0.0, time.time() - best[1])


def backup_is_fresh(backups: Path) -> bool:
    found = latest_backup(backups)
    return found is not None and found[1] <= BACKUP_MAX_AGE
