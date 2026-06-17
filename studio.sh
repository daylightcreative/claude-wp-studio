#!/usr/bin/env bash
# studio.sh — launch Claude WP Studio.
#
# Keeps Claude Code current, then launches it from this folder with the studio's defining
# default: BYPASS PERMISSIONS (full autonomy, no per-action prompts). This is what lets Claude
# do the technical work for you without stopping to ask on every step.
#
# The model (opus) and reasoning effort (xhigh) come from .claude/settings.json in this folder.
# To use the 1M-context model instead, change "opus" to "opus[1m]" there (needs a plan that
# includes 1M context). Bypass itself must live here in the launcher — Claude Code ignores it
# when set in a project settings file, for security.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

if ! command -v claude >/dev/null 2>&1; then
  echo "Claude Code isn't on your PATH yet."
  echo "Open a new Terminal window and run ./studio.sh again, or install it with:"
  echo "  curl -fsSL https://claude.ai/install.sh | bash"
  exit 1
fi

# Keep Claude Code up to date (the native installer also auto-updates in the background).
claude update >/dev/null 2>&1 || true

# Launch with full autonomy for this studio. Model + effort are read from .claude/settings.json.
exec claude --dangerously-skip-permissions "$@"
