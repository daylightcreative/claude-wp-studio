"""Split a shell command line into words and operators, the way a POSIX shell would.

Shared by the backup gate (guard.py) and the Bash hook (hooks.py). Differences from plain shlex
that matter for safety:
- a newline separates commands, as it does in the shell (shlex treats it as a space);
- `#` is an ordinary character, so a comment can't hide the rest of a line from the checker
  (the shell would ignore it; treating it as text only makes the check stricter);
- operators come out as their own tokens, so `ls>x` and `ls > x` look the same.
"""

from __future__ import annotations

import shlex
from typing import List, Optional

OPERATOR_CHARS = set(";&|<>()")
SEPARATORS = {";", "&&", "||", "|", "&"}


def tokenize(command: str) -> Optional[List[str]]:
    """Words and operators, or None when the command can't be split (an unclosed quote)."""
    lexer = shlex.shlex(command.replace("\r", "\n").replace("\n", " ; "), posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return None


def is_operator(token: str) -> bool:
    return bool(token) and set(token) <= OPERATOR_CHARS
