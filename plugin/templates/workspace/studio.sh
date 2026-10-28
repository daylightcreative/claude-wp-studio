#!/bin/sh
# Launch Claude WP Studio. (Kit-owned: the wp-studio plugin keeps this file up to date.)
#
# Auto mode: Claude works without asking about every step, while a safety check reviews each
# action and stops anything risky or irreversible for you to confirm. The studio's own rules
# (backups before changes, PHP checked before it goes live) are enforced by the wpsite tool.
cd "$(dirname "$0")" || exit 1
# Claude Code's installer puts `claude` in ~/.local/bin, which a new Terminal window may not have on PATH.
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) PATH="$HOME/.local/bin:$PATH" ;; esac
if ! command -v claude >/dev/null 2>&1; then
  echo "Claude Code isn't installed or isn't on your PATH yet. Open a new Terminal window and try again,"
  echo "or reinstall the studio: curl -fsSL https://get.daylightcreative.tech/wp-studio | bash"
  exit 1
fi
exec claude --permission-mode auto --settings .claude/launch-settings.json "$@"
