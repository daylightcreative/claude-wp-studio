#!/usr/bin/env bash
# db-pull.sh — dump the remote WordPress database to a local, timestamped .sql.gz.
#
# Read-only on the server (it just exports). Use it to:
#   - take a safety backup before any structural change, and
#   - pull the database down so Claude can inspect content offline (e.g. read every
#     page's stored block markup when planning a Divi → Gutenberg conversion).
#
# Usage:   ./db-pull.sh
# Output:  backups/db-YYYYMMDD-HHMMSS.sql.gz
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/.secrets/connection.env"

mkdir -p "$HERE/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HERE/backups/db-$STAMP.sql.gz"

# `wp db export -` streams the dump to stdout; we gzip it locally.
ssh -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" "cd '$WP_PATH' && wp db export -" | gzip > "$OUT"

echo "Wrote $OUT"
echo "Inspect without unzipping:  gunzip -c '$OUT' | less"
echo "Pull just page/post content instead (often handier for conversions):"
echo "  ./wp.sh post list --post_type=page --fields=ID,post_title"
echo "  ./wp.sh post get <ID> --field=content > backups/page-<ID>.html"
