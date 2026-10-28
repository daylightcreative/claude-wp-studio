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


UNQUOTED_SPECIAL = set("$`\\{}*?[]!")
WORD_START_SPECIAL = set("~#")


def literal_words(command: str) -> Optional[List[str]]:
    """Words and operators, or None unless every word is literal text.

    Stricter than tokenize(), for deciding that a command only reads: the remote shell would expand
    `$'…'`, `$(…)`, `${…}`, `{a,b}`, globs, `~` and backslash escapes into text nobody checked (a
    `$'-delete'` becomes `-delete`), so any of those outside single quotes means "can't judge".
    Single-quoted text is literal; double-quoted text is literal unless it holds `$`, a backtick or
    a backslash.
    """
    tokens: List[str] = []
    word: Optional[List[str]] = None
    index = 0
    text = command.replace("\r", "\n")
    while index < len(text):
        char = text[index]
        if char == "'":
            end = text.find("'", index + 1)
            if end < 0:
                return None
            word = (word or []) + list(text[index + 1:end])
            index = end + 1
            continue
        if char == '"':
            end = text.find('"', index + 1)
            if end < 0:
                return None
            inner = text[index + 1:end]
            if set(inner) & set("$`\\"):
                return None
            word = (word or []) + list(inner)
            index = end + 1
            continue
        if char in " \t" or char == "\n" or char in OPERATOR_CHARS:
            if word is not None:
                tokens.append("".join(word))
                word = None
            if char == "\n":
                tokens.append(";")
            elif char in OPERATOR_CHARS:
                op = char
                while index + 1 < len(text) and text[index + 1] in OPERATOR_CHARS:
                    index += 1
                    op += text[index]
                tokens.append(op)
            index += 1
            continue
        if char in UNQUOTED_SPECIAL or (word is None and char in WORD_START_SPECIAL):
            return None
        word = (word or []) + [char]
        index += 1
    if word is not None:
        tokens.append("".join(word))
    return tokens
