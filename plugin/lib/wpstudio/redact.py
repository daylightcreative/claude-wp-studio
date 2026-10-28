"""Strip secrets from remote output before it reaches the terminal (and so the chat).

Covers the WordPress secrets that commonly show up while working: the database password and the
auth keys and salts in wp-config.php, in source form (`define( 'DB_PASSWORD', '…' )`), in
`wp config list` tables and `wp config get` output, plus any value from the site's own connection
file (for example the SSH password) wherever it appears.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence

SECRET_CONSTANTS = (
    "DB_PASSWORD", "AUTH_KEY", "SECURE_AUTH_KEY", "LOGGED_IN_KEY", "NONCE_KEY",
    "AUTH_SALT", "SECURE_AUTH_SALT", "LOGGED_IN_SALT", "NONCE_SALT", "WP_CACHE_KEY_SALT",
)
_NAMES = "|".join(SECRET_CONSTANTS)
MASK = "[redacted]"

_DEFINE = re.compile(
    r"(define\s*\(\s*['\"](?:%s)['\"]\s*,\s*)(['\"])(?:\\.|(?!\2).)*\2" % _NAMES, re.I
)
# `wp config list` table rows and --format=dotenv / csv / json output.
_TABLE = re.compile(r"^(\s*\|?\s*(?:%s)\s*[|\t,=:]\s*)(\S.*?)(\s*(?:\|\s*constant\s*\|?)?\s*)$" % _NAMES)
_JSON = re.compile(r'("name"\s*:\s*"(?:%s)"\s*,\s*"value"\s*:\s*)"(?:\\.|[^"\\])*"' % _NAMES)


def redact_line(line: str, literals: Sequence[str] = ()) -> str:
    line = _DEFINE.sub(lambda m: m.group(1) + m.group(2) + MASK + m.group(2), line)
    line = _JSON.sub(lambda m: m.group(1) + '"' + MASK + '"', line)
    match = _TABLE.match(line)
    if match:
        line = match.group(1) + MASK + match.group(3)
    for value in literals:
        if value and len(value) >= 4 and value in line:
            line = line.replace(value, MASK)
    return line


def redact_text(text: str, literals: Sequence[str] = ()) -> str:
    return "\n".join(redact_line(line, literals) for line in text.split("\n"))


def wp_secret_get(args: Iterable[str]) -> bool:
    """True for `wp config get <SECRET>`, whose whole output is the secret."""
    words: List[str] = [a for a in args if not a.startswith("-")]
    if words[:1] == ["wp"]:
        words = words[1:]
    return len(words) >= 3 and words[0] == "config" and words[1] == "get" and words[2].upper() in SECRET_CONSTANTS
