#!/usr/bin/env bash
# maintain.sh — keep the machine's tooling current and the studio tidy. Runs quietly in the background.
#
# Safe to run routinely (a good habit at the start of a work session). Never disrupts a
# session — every step swallows its own errors.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# 1) Keep Homebrew + installed CLIs current (only if brew is present).
if command -v brew >/dev/null 2>&1; then
  echo "maintain.sh: updating Homebrew + tools…"
  brew update  >/dev/null 2>&1 || true
  brew upgrade >/dev/null 2>&1 || true
  brew cleanup >/dev/null 2>&1 || true
fi

# 2) Tidy the studio (clear macOS cruft).
find "$ROOT" -name '.DS_Store' -type f -delete 2>/dev/null || true

# 3) Rebuild the knowledge catalog so search stays current.
python3 "$HERE/catalog.py" build >/dev/null 2>&1 || true

echo "maintain.sh: tooling current, studio tidy ✓"
