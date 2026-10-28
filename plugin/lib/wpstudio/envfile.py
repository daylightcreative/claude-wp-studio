"""Read and write a site's connection file (in the secrets store: see workspace.secrets_dir).

Format: one `KEY='value'` per line, single-quoted with shell-style escaping of embedded quotes, so
the file is also safe to `source` from a shell. `#` lines are comments. Unquoted legacy values
(`KEY=value`) and double-quoted ones from the v1 kit are read too.

The file is written with mode 0600 inside a 0700 folder, atomically (temp file + rename), so a
crash never leaves a half-written secret file.
"""

from __future__ import annotations

import os
import re
import shlex
import tempfile
from pathlib import Path
from typing import Dict

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Keys `wpsite` understands. Anything else a site file holds is kept and listed, never used.
KNOWN_KEYS = (
    "SITE_URL",
    "SSH_HOST",
    "SSH_PORT",
    "SSH_USER",
    "SSH_PASSWORD",
    "SSH_KEY",
    "WP_PATH",
    "HOST",
)

# Everything else a site file holds (the SSH password, extra values the operator filed) is secret.
NON_SECRET_KEYS = frozenset({"SITE_URL", "SSH_HOST", "SSH_PORT", "SSH_USER", "WP_PATH", "HOST", "SSH_KEY"})


def secret_values(values: Dict[str, str]) -> list:
    return [v for k, v in values.items() if k not in NON_SECRET_KEYS and len(v) >= 4]


def _unquote(raw: str) -> str:
    """A value with shell rules: quotes removed, a trailing `# comment` dropped. v1 files were read
    with `source`, so lines like `SSH_PORT='22'   # custom port` are valid and mean 22."""
    try:
        words = shlex.split(raw, comments=True, posix=True)
    except ValueError:
        return raw.strip()
    return " ".join(words)


def _quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def read(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export "):]
        key, sep, raw = stripped.partition("=")
        key = key.strip()
        if not sep or not KEY_RE.match(key):
            continue
        values[key] = _unquote(raw)
    return values


def write(path: Path, values: Dict[str, str], header: str = "") -> None:
    for key in values:
        if not KEY_RE.match(key):
            raise ValueError("invalid key name: %r" % key)
        if "\n" in values[key] or "\r" in values[key]:
            raise ValueError("value for %s contains a line break" % key)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    ordered = [k for k in KNOWN_KEYS if k in values] + sorted(k for k in values if k not in KNOWN_KEYS)
    lines = []
    if header:
        lines.extend("# " + h if h else "#" for h in header.splitlines())
    lines.extend("%s=%s" % (k, _quote(values[k])) for k in ordered)
    fd, tmp = tempfile.mkstemp(prefix=".env-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    os.chmod(path, 0o600)
