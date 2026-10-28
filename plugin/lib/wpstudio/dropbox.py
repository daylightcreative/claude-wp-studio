"""The credential drop box (`CREDENTIALS.txt` at the studio root).

The operator pastes connection details below the marker line. `wpsite secrets file <site>` parses
them, merges them into that site's connection file and resets the drop box to its blank template.
Nothing here ever prints a value: reports name fields, never contents. Claude is blocked from
reading the drop box itself (permission deny rules plus the plugin's Bash hook), so a password
pasted here goes from the operator's keyboard to the site's 0600 file without entering the chat.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

from . import PLUGIN_ROOT

MARKER = "PASTE BELOW THIS LINE"
TEMPLATE = PLUGIN_ROOT / "templates" / "workspace" / "CREDENTIALS.txt"

# Normalized label -> connection key. Labels are lowercased with punctuation turned into spaces.
LABELS = {
    "SITE_URL": ("site address", "site url", "url", "website", "site", "address", "home url", "web address"),
    "SSH_HOST": ("ssh host", "sftp host", "host", "hostname", "host name", "server", "ip", "ip address",
                 "server address", "ssh ip", "sftp ip"),
    "SSH_PORT": ("ssh port", "sftp port", "port"),
    "SSH_USER": ("ssh username", "ssh user", "sftp username", "sftp user", "username", "user", "user name",
                 "login"),
    "SSH_PASSWORD": ("ssh password", "sftp password", "password", "pass", "pw"),
    "WP_PATH": ("wordpress folder on the server", "wordpress folder", "wordpress path", "wp path", "path",
                "web root", "document root", "root path", "site path"),
    "HOST": ("hosting company", "host company", "hosting", "hosting provider", "provider", "host provider"),
    "SSH_KEY": ("ssh key", "ssh key file", "key file", "private key", "private key path"),
}
LABEL_TO_KEY = {label: key for key, labels in LABELS.items() for label in labels}

# The connect line hosts show you to copy, e.g. `ssh user@203.0.113.5 -p 12345`.
SSH_LINE = re.compile(
    r"\bssh\s+(?:-p\s*(?P<p1>\d+)\s+)?(?P<user>[\w.+-]+)@(?P<host>[\w.-]+)(?:\s+-p\s*(?P<p2>\d+))?"
)


class DropboxError(Exception):
    pass


@dataclass
class Parsed:
    values: Dict[str, str] = field(default_factory=dict)
    unrecognized_lines: int = 0
    refused: List[str] = field(default_factory=list)


def _norm_label(label: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", label.lower()).split())


def _clean(key: str, value: str) -> str:
    value = value.strip()
    if key != "SSH_PASSWORD":
        value = value.strip("`\"'")
    if key == "SITE_URL":
        if not re.match(r"^https?://", value, re.I):
            value = "https://" + value
        parsed = urlparse(value)
        value = "%s://%s%s" % (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"))
    elif key == "SSH_PORT":
        if not value.isdigit() or not 0 < int(value) < 65536:
            raise DropboxError("The SSH port must be a number between 1 and 65535.")
    elif key == "HOST":
        value = value.lower()
    elif key == "SSH_KEY":
        value = str(Path(value).expanduser())
    return value


def payload_lines(text: str) -> List[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if MARKER in line:
            # Skip the marker and the rule line drawn under it.
            rest = lines[index + 1:]
            if rest and set(rest[0].strip()) <= set("─-=_ "):
                rest = rest[1:]
            return rest
    raise DropboxError("CREDENTIALS.txt doesn't have its 'PASTE BELOW THIS LINE' marker. Reset it with: wpsite secrets wipe")


def parse(text: str) -> Parsed:
    result = Parsed()
    in_key_block = False
    for line in payload_lines(text):
        stripped = line.strip()
        if not stripped:
            continue
        if "PRIVATE KEY-----" in stripped:
            in_key_block = "BEGIN" in stripped
            if "BEGIN" in stripped:
                result.refused.append("a pasted private key (save it as a file and put its path on the 'SSH key' line)")
            continue
        if in_key_block:
            continue
        match = SSH_LINE.search(stripped)
        if match and ":" not in stripped.split("ssh", 1)[0]:
            result.values["SSH_USER"] = match.group("user")
            result.values["SSH_HOST"] = match.group("host")
            port = match.group("p1") or match.group("p2")
            if port:
                result.values["SSH_PORT"] = port
            continue
        label, sep, value = stripped.partition(":")
        if not sep:
            result.unrecognized_lines += 1
            continue
        key = LABEL_TO_KEY.get(_norm_label(label))
        if key is None:
            # "https://…" lines split on the scheme colon; treat a bare URL as the site address.
            if _norm_label(label) in ("http", "https") and value.startswith("//"):
                key, value = "SITE_URL", stripped
            else:
                norm = _norm_label(label).upper().replace(" ", "_")
                if not norm or not value.strip():
                    result.unrecognized_lines += 1
                    continue
                key = "EXTRA_" + norm[:40]
        if not value.strip():
            continue  # a template line left blank
        result.values[key] = value.strip() if key.startswith("EXTRA_") else _clean(key, value)
    return result


def has_content(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        parsed = parse(path.read_text(encoding="utf-8"))
    except DropboxError:
        return True  # an unrecognized file is treated as holding something
    return bool(parsed.values or parsed.unrecognized_lines or parsed.refused)


def wipe(path: Path) -> None:
    shutil.copyfile(TEMPLATE, path)
    path.chmod(0o600)


def ensure(path: Path) -> None:
    if not path.exists():
        wipe(path)
