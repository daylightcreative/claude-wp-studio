"""Refuse a commit that would put a secret, a database dump or a site config into git.

Three checks over the staged files:
1. Literal values: every secret the studio actually holds (SSH passwords and other filed values
   from projects/*/.secrets/*.env) is searched for verbatim. This is the precise check: it catches
   a real password copied into a note, whatever the surrounding text looks like.
2. Patterns: private keys, wp-config secrets, well-known token formats, WordPress application
   passwords.
3. Files that never belong in the backup: database dumps, wp-config.php copies, .env and key
   files, and anything over GitHub's push limits.

Findings name the file and line, never the value.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Sequence, Tuple

from . import envfile

MAX_FILE_BYTES = 50 * 1024 * 1024
SCAN_BYTES = 5 * 1024 * 1024
NON_SECRET_KEYS = {"SITE_URL", "SSH_HOST", "SSH_PORT", "SSH_USER", "WP_PATH", "HOST", "SSH_KEY"}

PATTERNS: Sequence[Tuple[str, "re.Pattern[str]"]] = (
    ("a private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("a WordPress database password or salt",
     re.compile(r"define\s*\(\s*['\"](DB_PASSWORD|AUTH_KEY|SECURE_AUTH_KEY|LOGGED_IN_KEY|NONCE_KEY|AUTH_SALT|"
                r"SECURE_AUTH_SALT|LOGGED_IN_SALT|NONCE_SALT)['\"]\s*,\s*['\"][^'\"\[]{4,}['\"]", re.I)),
    ("an AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("a GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("a Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("a Stripe live key", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}")),
    ("a Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("a WordPress application password", re.compile(r"(?<![\w])[A-Za-z0-9]{4}( [A-Za-z0-9]{4}){5}(?![\w])")),
)
PLACEHOLDER = re.compile(r"x{4}|example|placeholder|your[-_ ]|<[^>]+>|\.\.\.|\*{3}|\[redacted\]", re.I)

BLOCKED_FILES = (
    (re.compile(r"(^|/)wp-config\.php$"), "a wp-config.php copy (it holds the database password)"),
    (re.compile(r"\.sql(\.gz|\.zip|\.bz2|\.xz)?$", re.I), "a database dump"),
    (re.compile(r"(^|/)\.env(\.[\w-]+)?$"), "an .env file"),
    (re.compile(r"\.(pem|p12|pfx|key)$", re.I), "a key file"),
    (re.compile(r"(^|/)id_(rsa|ed25519|ecdsa|dsa)(\.pub)?$"), "an SSH key"),
    (re.compile(r"(^|/)\.secrets/"), "a studio secrets file"),
    (re.compile(r"(^|/)CREDENTIALS\.txt$"), "the credential drop box"),
)


@dataclass
class Finding:
    path: str
    line: int
    reason: str

    def __str__(self) -> str:
        where = self.path if self.line == 0 else "%s:%d" % (self.path, self.line)
        return "%s: %s" % (where, self.reason)


def known_secrets(root: Path) -> List[str]:
    values = []
    for env in (root / "projects").glob("*/.secrets/*.env"):
        try:
            data = envfile.read(env)
        except (OSError, UnicodeDecodeError):
            continue
        values.extend(v for k, v in data.items() if k not in NON_SECRET_KEYS and len(v) >= 6)
    return sorted(set(values), key=len, reverse=True)


def scan_text(path: str, text: str, secrets: Sequence[str]) -> List[Finding]:
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for value in secrets:
            if value in line:
                findings.append(Finding(path, number, "contains a secret the studio holds for a site"))
                break
        for reason, pattern in PATTERNS:
            match = pattern.search(line)
            if match and not PLACEHOLDER.search(match.group(0)):
                findings.append(Finding(path, number, "looks like %s" % reason))
    return findings


def scan_files(entries: Iterable[Tuple[str, int, bytes]], secrets: Sequence[str]) -> List[Finding]:
    """Each entry is (repo-relative path, size in bytes, the first SCAN_BYTES of content)."""
    findings: List[Finding] = []
    for path, size, data in entries:
        posix = str(PurePosixPath(path))
        for pattern, reason in BLOCKED_FILES:
            if pattern.search(posix):
                findings.append(Finding(posix, 0, "is %s and never belongs in the backup" % reason))
                break
        if size > MAX_FILE_BYTES:
            findings.append(Finding(posix, 0, "is %.0f MB; GitHub refuses files this large, so the backup would "
                                              "stop working (keep it out of the studio folder)" % (size / 1e6)))
            continue
        if b"\0" in data[:8192]:
            continue  # binary
        findings.extend(scan_text(posix, data.decode("utf-8", "replace"), secrets))
    return findings


def staged_entries(root: Path) -> List[Tuple[str, int, bytes]]:
    names = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
                           capture_output=True, check=True).stdout.split(b"\0")
    entries = []
    for raw in names:
        if not raw:
            continue
        name = raw.decode("utf-8", "surrogateescape")
        size_out = subprocess.run(["git", "-C", str(root), "cat-file", "-s", ":" + name], capture_output=True, text=True)
        size = int(size_out.stdout.strip() or 0)
        blob = subprocess.run(["git", "-C", str(root), "show", ":" + name], capture_output=True).stdout[:SCAN_BYTES]
        entries.append((name, size, blob))
    return entries


def scan_staged(root: Path) -> List[Finding]:
    return scan_files(staged_entries(root), known_secrets(root))
