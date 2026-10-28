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
from typing import List, Optional, Tuple

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

# Token kinds from literal_words(). Only OP tokens separate or redirect: a quoted ';' is a WORD.
OP, WORD, FD = "op", "word", "fd"


def literal_words(command: str) -> Optional[List[Tuple[str, str]]]:
    """(kind, text) tokens, or None unless every word is literal text.

    Stricter than tokenize(), for deciding that a command only reads: the remote shell would expand
    `$'…'`, `$(…)`, `${…}`, `{a,b}`, globs, `~` and backslash escapes into text nobody checked (a
    `$'-delete'` becomes `-delete`), so any of those outside single quotes means "can't judge".
    Single-quoted text is literal; double-quoted text is literal unless it holds `$`, a backtick or
    a backslash. Tokens are typed so quoted text can never pass for an operator, and a number
    counts as a file descriptor only when it touches the redirection (`2>`), as in the shell. A
    carriage return is ordinary text to the shell but a line break to people reading the command,
    so it means "can't judge" too.
    """
    if "\r" in command:
        return None
    tokens: List[Tuple[str, str]] = []
    word: Optional[List[str]] = None
    quoted = False
    index = 0
    text = command

    def finish():
        nonlocal word, quoted
        if word is not None:
            joined = "".join(word)
            touching = index < len(text) and text[index] in "<>"
            kind = FD if (not quoted and joined.isdigit() and touching) else WORD
            tokens.append((kind, joined))
        word, quoted = None, False

    while index < len(text):
        char = text[index]
        if char == "'":
            end = text.find("'", index + 1)
            if end < 0:
                return None
            word = (word or []) + list(text[index + 1:end])
            quoted = True
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
            quoted = True
            index = end + 1
            continue
        if char in " \t\n" or char in OPERATOR_CHARS:
            finish()
            if char == "\n":
                tokens.append((OP, ";"))
            elif char in OPERATOR_CHARS:
                op = char
                while index + 1 < len(text) and text[index + 1] in OPERATOR_CHARS:
                    index += 1
                    op += text[index]
                tokens.append((OP, op))
            index += 1
            continue
        if char in UNQUOTED_SPECIAL or (word is None and char in WORD_START_SPECIAL):
            return None
        word = (word or []) + [char]
        index += 1
    finish()
    return tokens
