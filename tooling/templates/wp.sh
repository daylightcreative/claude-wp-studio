#!/usr/bin/env bash
# wp.sh — run any WP-CLI command on the remote WordPress site over SSH.
#
# This is the fastest, most authoritative way to work on a site — no dashboard needed.
# WP-CLI runs against the database directly, so no WordPress login is required.
#
# Usage:
#   ./wp.sh plugin list
#   ./wp.sh theme list
#   ./wp.sh post list --post_type=page --fields=ID,post_title,post_status
#   ./wp.sh option get template
#   ./wp.sh db query "SELECT COUNT(*) FROM wp_posts WHERE post_type='page'"
#
# For commands with complex/JSON arguments, prefer piping content over stdin from a file
# (see library/lessons/wordpress_safety_and_backups.md) rather than inlining it here.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/.secrets/connection.env"

# Build a properly-quoted remote command from all arguments.
REMOTE_ARGS="$(printf '%q ' "$@")"

ssh -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" "cd '$WP_PATH' && wp $REMOTE_ARGS"

# --- Gotcha note ---------------------------------------------------------------
# If you ever see "REMOTE HOST IDENTIFICATION HAS CHANGED" (Kinsta rotates host keys),
# clear and re-trust the key, then retry:
#   ssh-keygen -R "[$SSH_HOST]:$SSH_PORT"
#   ssh -p "$SSH_PORT" -o StrictHostKeyChecking=accept-new "$SSH_USER@$SSH_HOST" true
# Details: library/lessons/ssh_sftp_and_access_gotchas.md
