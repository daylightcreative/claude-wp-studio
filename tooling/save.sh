#!/usr/bin/env bash
# save.sh — auto-save the whole studio: commit everything locally, and push to the private
# GitHub backup if one is linked. Run after a meaningful chunk of work and at session end.
#
# Designed to NEVER disrupt a session: if anything fails (no remote yet, offline, GitHub not
# connected), it saves locally and exits cleanly. .gitignore keeps secrets and dumps out.
#
# Usage:
#   tooling/save.sh                       # auto message
#   tooling/save.sh "Rebuilt the home page"   # custom message
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT" || exit 0

# Must be a git repo.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "save.sh: not a git repo yet (skipping)"; exit 0; }

# Ensure a commit identity exists. A fresh Mac often has no global git identity, which would
# make `git commit` fail and silently break backups. Set a neutral local one only if none is.
git config user.email >/dev/null 2>&1 || git config user.email "wp-studio@localhost"
git config user.name  >/dev/null 2>&1 || git config user.name  "Claude WP Studio"

# Stage everything. .gitignore keeps secrets and DB dumps out.
git add -A

# Nothing to save? done.
if git diff --cached --quiet; then
  exit 0
fi

MSG="${1:-Studio update $(date '+%Y-%m-%d %H:%M')}"
git commit -m "$MSG" >/dev/null 2>&1 || { echo "save.sh: commit skipped"; exit 0; }
echo "save.sh: committed — $MSG"

# Push only if an 'origin' remote exists, using whatever GitHub auth the operator set up
# (gh auth login configures git's credential helper). Never fail the session if push doesn't
# work — the commit is already saved locally and the next save retries.
if git remote get-url origin >/dev/null 2>&1; then
  if git push -q origin HEAD 2>/dev/null; then
    echo "save.sh: backed up to GitHub ✓"
  else
    echo "save.sh: saved locally; GitHub push didn't go through, will retry next time (see guides/04_git_and_backup.md)"
  fi
else
  echo "save.sh: saved locally; no GitHub backup linked yet (see guides/04_git_and_backup.md)"
fi
