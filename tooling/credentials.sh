#!/usr/bin/env bash
# credentials.sh — helper for the credential drop box (CREDENTIALS.txt at the studio root).
#
# The drop box is where the operator pastes a secret so it never goes into the chat. The flow:
# the operator pastes below the marker line → Claude reads it and files it into the right
# project's git-ignored .secrets/connection.env → Claude wipes the drop box back to blank.
#
# CREDENTIALS.txt is git-ignored (a filled one must never be committed); the blank template
# ships as CREDENTIALS.txt.template. This helper creates the live file from the template if
# it's missing, and wipes it back to the template.
#
# Usage:
#   tooling/credentials.sh status    # is anything pasted in the drop box?
#   tooling/credentials.sh payload   # print what's pasted (everything below the marker)
#   tooling/credentials.sh wipe      # reset the drop box to its blank template
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BOX="$ROOT/CREDENTIALS.txt"
TEMPLATE="$ROOT/CREDENTIALS.txt.template"

# Create the live drop box from the template if it doesn't exist yet.
_ensure_box() {
  [ -f "$BOX" ] && return 0
  if [ -f "$TEMPLATE" ]; then cp "$TEMPLATE" "$BOX"; return 0; fi
  return 1
}

_marker_line() { grep -n "PASTE BELOW THIS LINE" "$BOX" 2>/dev/null | head -1 | cut -d: -f1; }

cmd="${1:-help}"
case "$cmd" in
  status)
    _ensure_box || { echo "drop box: missing and no template found"; exit 1; }
    m="$(_marker_line)"
    [ -n "$m" ] || { echo "drop box: format unrecognized"; exit 1; }
    payload="$(tail -n +"$((m + 2))" "$BOX" | tr -d '[:space:]')"
    if [ -n "$payload" ]; then
      echo "drop box: HAS CONTENT (something is pasted — read it, file it, then wipe)"
    else
      echo "drop box: empty"
    fi
    ;;
  payload|show)
    _ensure_box || { echo "drop box: missing and no template found"; exit 1; }
    m="$(_marker_line)"
    [ -n "$m" ] || { echo "drop box: format unrecognized"; exit 1; }
    tail -n +"$((m + 2))" "$BOX"
    ;;
  wipe)
    # Prefer restoring the exact blank template; fall back to truncating after the marker.
    if [ -f "$TEMPLATE" ]; then
      cp "$TEMPLATE" "$BOX"
      echo "credentials.sh: drop box reset to blank template ✓"
    else
      _ensure_box || { echo "drop box: missing and no template found"; exit 1; }
      m="$(_marker_line)"
      [ -n "$m" ] || { echo "credentials.sh: can't find the marker; not wiping"; exit 1; }
      tmp="$(mktemp)"
      head -n "$((m + 1))" "$BOX" > "$tmp"   # keep header through the dashed separator after the marker
      printf '\n' >> "$tmp"
      mv "$tmp" "$BOX"
      echo "credentials.sh: drop box wiped back to blank ✓"
    fi
    ;;
  *)
    echo "Usage: credentials.sh {status | payload | wipe}"
    echo "  status   — is anything pasted in the drop box?"
    echo "  payload  — print what's pasted (everything below the marker)"
    echo "  wipe     — reset the drop box to its blank template"
    ;;
esac
