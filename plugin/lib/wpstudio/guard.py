"""Decide whether a remote command can change a site, and whether a fresh backup covers it.

Rule: anything that can change a site needs a verified database backup of that environment taken
in the last BACKUP_MAX_AGE. The read-only side is an explicit allowlist; everything else counts as
a change. When in doubt it fails closed, so a command this module has never heard of is treated
as a change.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from . import shellwords

BACKUP_MAX_AGE = 2 * 60 * 60  # seconds
BACKUP_GLOB = "db-*.sql.gz"
VERIFIED_SUFFIX = ".verified.json"

# WP-CLI commands that only read, keyed by command path. A value of None means every subcommand
# under that path reads; a set lists the subcommands that read. Only core WP-CLI commands are here:
# a plugin's own commands can do anything.
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
    ("db",): {"size", "tables", "columns", "prefix", "search"},
    ("cron", "event"): {"list"},
    ("cron", "schedule"): {"list"},
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
    ("cli",): {"version", "info", "has-command"},
    ("help",): None,
    ("package",): {"list", "path"},
}
# Cache clearing changes nothing a backup would restore, so it never needs one.
WP_CACHE_SAFE = {
    ("cache", "flush"), ("kinsta", "cache", "purge"), ("litespeed-purge",), ("rocket", "clean"),
    ("w3-total-cache", "flush"), ("super-cache", "flush"), ("sg", "purge"),
}
# Flags allowed on a read. WP-CLI's global flags include --exec and --require (run arbitrary PHP),
# --ssh and --http (run somewhere else) and --path, so anything not listed here makes the command
# count as a change. Names with an underscore are field filters on list commands (--post_type=page).
WP_SAFE_FLAGS = {
    "format", "fields", "field", "status", "number", "orderby", "order", "search", "search-columns",
    "role", "skip-plugins", "skip-themes", "skip-packages", "quiet", "url", "user", "debug", "color",
    "no-color", "all", "type", "name", "per-page", "network", "porcelain", "strict", "raw", "include",
    "exclude", "page", "limit", "offset", "prefix", "all-tables", "all-tables-with-prefix", "regex",
    "regex-flags", "regex-delimiter", "scope", "dry-run", "report", "report-changed-only", "precise",
    "skip-columns", "include-columns", "skip-tables", "minor", "major", "patch", "force-check",
    "detail", "human-readable", "decimals", "size_format", "tables", "post_type", "version", "info",
    "matching", "stable", "context",
}
WP_UNSAFE_FLAGS = {"exec", "require", "ssh", "http", "path", "prompt", "skip-wordpress"}
DUMP_SAFE_FLAGS = {"single-transaction", "quick", "add-drop-table", "tables", "exclude_tables", "porcelain",
                   "skip-plugins", "skip-themes", "quiet"}


def _flag_name(arg: str) -> str:
    return arg[2:].split("=", 1)[0]


def _safe_flag(arg: str, allowed=None) -> bool:
    if not arg.startswith("--"):
        return False  # short flags and anything else unknown
    name = _flag_name(arg)
    if name in WP_UNSAFE_FLAGS:
        return False
    if allowed is not None:
        return name in allowed
    return name in WP_SAFE_FLAGS or ("_" in name and re.match(r"^[a-z][a-z0-9_]*$", name) is not None)


def wp_command_path(args: Sequence[str]) -> List[str]:
    """The command words of a WP-CLI invocation (`post meta list`), up to the first argument."""
    words = []
    for arg in args:
        if arg.startswith("-"):
            continue
        if not re.match(r"^[a-z][a-z0-9-]*$", arg):
            break
        words.append(arg)
    return words


def wp_is_read_only(args: Sequence[str]) -> bool:
    args = list(args)
    if args[:1] == ["wp"]:
        args = args[1:]
    if not args:
        return True
    if args in (["--info"], ["--version"]):
        return True
    positional = [a for a in args if a == "-" or not a.startswith("-")]
    flags = [a for a in args if a.startswith("-") and a != "-"]
    if positional and positional[0].startswith("@"):
        return False  # an alias: the command runs on whatever site the alias names
    words = wp_command_path(args)
    if not words:
        return False
    for size in (3, 2, 1):
        if tuple(words[:size]) in WP_CACHE_SAFE:
            return all(_safe_flag(f) for f in flags)
    if words[:2] == ["db", "query"] or words[:1] == ["sql"]:
        # The SQL goes to the mysql client, which runs its own commands inside the text (\g starts a
        # new statement, \! runs a shell command, \T writes a file) and hands it flags such as
        # --init-command. No SQL text is judged read-only; use `db tables`, `db size`, `db search`.
        return False
    if words[:2] == ["db", "export"]:
        # `wp db export -` streams to stdout; a file target writes a dump on the server, and
        # mysqldump flags such as --result-file write files too.
        return positional[2:] == ["-"] and all(_safe_flag(f, DUMP_SAFE_FLAGS) for f in flags)
    if not all(_safe_flag(f) for f in flags):
        return False
    if words[0] == "search-replace":
        return "--dry-run" in flags
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


# Programs `wpsite sh` may run without a backup. Each maps to a check of its arguments; programs
# that can write a file with the right flag (sed, sort, tee, tree, mysql, …) aren't here at all.
def _no(*bad):
    """Refuse the given options, including inside a cluster of short flags (-mC contains -C)."""
    shorts = {b[1] for b in bad if len(b) == 2 and b[0] == "-" and b[1] != "-"}
    def check(args):
        for a in args:
            if any(a == b or a.startswith(b) for b in bad):
                return False
            if a.startswith("-") and not a.startswith("--") and shorts & set(a[1:]):
                return False
        return True
    return check


def _only_flags(*allowed):
    return lambda args: all(a in allowed for a in args if a.startswith("-"))


SHELL_READ = {
    **{p: (lambda args: True) for p in (
        "ls", "cat", "head", "tail", "grep", "egrep", "fgrep", "zgrep", "stat", "wc", "du", "df", "md5sum",
        "sha1sum", "sha256sum", "pwd", "echo", "printf", "whoami", "id", "uname", "test", "[", "cut", "tr",
        "zcat", "readlink", "realpath", "basename", "dirname", "strings", "od", "hexdump", "ps", "uptime",
        "free", "nproc", "true", "false", "diff", "cmp", "nl", "rev")},
    "find": _no("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fls"),
    "file": _no("-C", "--compile"),
    "date": _no("-s", "--set"),
    "php": lambda args: bool(args) and _only_flags("-v", "-l", "-m", "-i", "--version", "--ini")(args)
                        and any(a in ("-v", "-l", "-m", "-i", "--version", "--ini") for a in args),
    "gzip": lambda args: _only_flags("-l", "-t", "--list", "--test")(args) and any(a.startswith("-") for a in args),
    "tar": lambda args: _only_flags("-t", "-tf", "-tvf", "-tzf", "-tzvf", "-ztf", "-ztvf", "--list")(args)
                        and any(a.startswith("-") for a in args),
    "crontab": lambda args: args == ["-l"],
    "wp": wp_is_read_only,
}


# Programs that print wp-config.php's text unchanged, so masking by value still recognises the
# secrets in it. Anything else naming the file (rev, tr, od…) counts as a change.
CONFIG_SAFE_READERS = {"grep", "egrep", "fgrep", "cat", "head", "tail", "ls", "stat", "wc", "md5sum", "sha1sum",
                       "sha256sum", "find", "test", "[", "php", "file"}


def _simple_commands(command: str) -> Optional[List[List[str]]]:
    """Split into simple commands, dropping harmless redirections. None means "can't judge"."""
    if re.search(r"\$\(|`|\$\{|<\(|>\(", command):
        return None
    tokens = shellwords.literal_words(command)
    if tokens is None:
        return None
    commands: List[List[str]] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        nxt = tokens[index + 1] if index + 1 < len(tokens) else None
        if token.isdigit() and nxt in (">", ">>", ">&", "<"):
            index += 1  # a file-descriptor number before a redirection
            continue
        if not shellwords.is_operator(token):
            commands[-1].append(token)
        elif token in shellwords.SEPARATORS:
            commands.append([])
        elif token in (">", ">>", "&>", "&>>"):
            if nxt != "/dev/null":
                return None
            index += 1
        elif token == ">&":
            if nxt not in ("1", "2"):
                return None
            index += 1
        elif token == "<":
            if nxt is None or shellwords.is_operator(nxt):
                return None
            index += 1
        else:
            return None  # >|, |&, ( ), << and anything else: not something to wave through
        index += 1
    return [c for c in commands if c]


def config_output_is_maskable(command: str) -> bool:
    """False when a command names wp-config.php and could print its text transformed (reversed,
    re-cased, hex-dumped), which masking by value can't recognise."""
    if "wp-config" not in command.lower():
        return True
    commands = _simple_commands(command)
    return commands is not None and all(w[0] in CONFIG_SAFE_READERS or w[0] == "cd" for w in commands)


def shell_is_read_only(command: str) -> bool:
    commands = _simple_commands(command)
    if commands is None:
        return False
    names_config = any("wp-config" in word.lower() for words in commands for word in words)
    for words in commands:
        if names_config and words[0] not in CONFIG_SAFE_READERS and words[0] != "cd":
            return False  # could print wp-config.php's secrets in a form masking by value misses
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            return False  # VAR=value can change how the next program behaves (WP_CLI_PHP_ARGS, LD_PRELOAD…)
        program = words[0]
        if program == "cd":
            continue
        if "/" in program or program not in SHELL_READ:
            return False
        if not SHELL_READ[program](words[1:]):
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
