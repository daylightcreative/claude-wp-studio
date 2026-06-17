#!/usr/bin/env bash
#
#   Claude WP Studio — installer
#   https://github.com/daylightcreative/claude-wp-studio
#
#   One-line install:
#       curl -fsSL https://get.daylightcreative.tech/wp-studio | bash
#
#   What it does (macOS):
#     1. Installs the prerequisites (Xcode CLT, Homebrew, a MODERN Python, WordPress tooling)
#     2. Installs the latest Claude Code (native installer — auto-updates over time)
#     3. Lays down the studio (knowledge library, tooling, standards) in a folder you choose
#     4. Writes the Claude Code defaults: xhigh reasoning effort + the launcher's bypass mode
#     5. Optionally connects a private GitHub backup (your own account)
#     6. Hands off to Claude's login so you can connect your subscription or API key
#
#   Flags / env (for unattended / agent-driven installs):
#     --unattended            accept all defaults, no prompts
#     --dir <path>            install location (default: ~/claude-wp-studio)
#     --no-backup             skip the GitHub backup step
#     --owner <gh-owner>      source GitHub owner (default below)
#     CLAUDE_WP_STUDIO_DIR    same as --dir
#     CLAUDE_WP_STUDIO_OWNER  same as --owner
#
set -uo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
GH_OWNER="${CLAUDE_WP_STUDIO_OWNER:-daylightcreative}"   # published source GitHub owner
REPO_NAME="claude-wp-studio"
DEFAULT_DIR="$HOME/claude-wp-studio"
LOG="$HOME/.claude-wp-studio-install.log"

UNATTENDED=0
NO_BACKUP=0
STUDIO_DIR="${CLAUDE_WP_STUDIO_DIR:-}"

# ─── Args ────────────────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --unattended) UNATTENDED=1 ;;
    --no-backup)  NO_BACKUP=1 ;;
    --dir)        STUDIO_DIR="${2:-}"; shift ;;
    --owner)      GH_OWNER="${2:-}"; shift ;;
    -h|--help)    grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" ;;
  esac
  shift
done

TARBALL_URL="https://github.com/${GH_OWNER}/${REPO_NAME}/archive/refs/heads/main.tar.gz"

# ─── Output helpers ──────────────────────────────────────────────────────────
BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
say()  { printf '%s\n' "$*"; printf '%s\n' "$(date '+%F %T') $*" >> "$LOG" 2>/dev/null || true; }
step() { printf '\n%s▸ %s%s\n' "$BOLD" "$*" "$RESET"; printf '%s\n' "$(date '+%F %T') STEP: $*" >> "$LOG" 2>/dev/null || true; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '  %s!%s %s\n' "$YELLOW" "$RESET" "$*"; }
die()  { printf '\n%sInstall stopped:%s %s\n' "$RED" "$RESET" "$*"; exit 1; }

# Read a prompt from the real terminal even when piped via `curl | bash`.
ask() { # ask "Question" "default" -> echoes answer
  local q="$1" def="${2:-}" ans=""
  if [ "$UNATTENDED" = "1" ] || [ ! -r /dev/tty ]; then printf '%s' "$def"; return; fi
  printf '%s%s%s ' "$BOLD" "$q" "$RESET" > /dev/tty
  [ -n "$def" ] && printf '%s[%s]%s ' "$DIM" "$def" "$RESET" > /dev/tty
  read -r ans < /dev/tty || ans=""
  printf '%s' "${ans:-$def}"
}
confirm() { # confirm "Question" -> returns 0 (yes) / 1 (no); defaults to yes
  local a; a="$(ask "$1 (Y/n)" "Y")"
  case "$a" in [nN]|[nN][oO]) return 1 ;; *) return 0 ;; esac
}

# ─── Banner ──────────────────────────────────────────────────────────────────
printf '\n%s┌────────────────────────────────────────────┐%s\n' "$BOLD" "$RESET"
printf '%s│           Claude WP Studio — install         │%s\n' "$BOLD" "$RESET"
printf '%s└────────────────────────────────────────────┘%s\n' "$BOLD" "$RESET"
say "A ready-to-work WordPress studio for Claude Code."
say "Log: $LOG"
: > "$LOG" 2>/dev/null || true

# ─── 1. Preflight ────────────────────────────────────────────────────────────
step "Checking your system"
[ "$(uname -s)" = "Darwin" ] || die "This installer currently supports macOS only."
ARCH="$(uname -m)"
ok "macOS on $ARCH"

# ─── 2. Xcode Command Line Tools (provides git) ──────────────────────────────
step "Command Line Tools"
if xcode-select -p >/dev/null 2>&1; then
  ok "already installed"
else
  warn "installing Xcode Command Line Tools — a system dialog will appear; click Install"
  xcode-select --install >/dev/null 2>&1 || true
  say "  Waiting for Command Line Tools to finish installing…"
  until xcode-select -p >/dev/null 2>&1; do sleep 10; done
  ok "installed"
fi

# ─── 3. Homebrew ─────────────────────────────────────────────────────────────
step "Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  warn "installing Homebrew…"
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
    >>"$LOG" 2>&1 || die "Homebrew install failed (see $LOG)."
fi
# Put brew on PATH for this session (and persist for new shells).
if [ -x /opt/homebrew/bin/brew ]; then BREW=/opt/homebrew/bin/brew
elif [ -x /usr/local/bin/brew ]; then BREW=/usr/local/bin/brew
else die "Homebrew not found after install."; fi
eval "$("$BREW" shellenv)"
if ! grep -q 'brew shellenv' "$HOME/.zprofile" 2>/dev/null; then
  printf '\neval "$(%s shellenv)"\n' "$BREW" >> "$HOME/.zprofile"
fi
ok "Homebrew ready ($("$BREW" --version | head -1))"

# ─── 4. Modern Python (NOT macOS system Python) ──────────────────────────────
step "Python (modern, via Homebrew)"
brew list python >/dev/null 2>&1 || brew install python >>"$LOG" 2>&1 || warn "python install reported an issue (see $LOG)"
hash -r
if python3 -c "import sqlite3" >/dev/null 2>&1; then
  ok "python3 $(python3 --version 2>&1 | awk '{print $2}') with sqlite3 ✓  ($(command -v python3))"
else
  die "A working python3 with sqlite3 is required (see $LOG)."
fi

# ─── 5. WordPress + dev tooling ──────────────────────────────────────────────
step "WordPress + dev tooling"
for f in wp-cli imagemagick mysql-client gh rsync git; do
  if brew list "$f" >/dev/null 2>&1; then
    ok "$f"
  else
    say "  installing $f…"
    brew install "$f" >>"$LOG" 2>&1 && ok "$f" || warn "$f install reported an issue (see $LOG)"
  fi
done

# ─── 6. Claude Code (latest; native installer auto-updates) ───────────────────
step "Claude Code"
if command -v claude >/dev/null 2>&1; then
  ok "already installed — updating"
  claude update >>"$LOG" 2>&1 || true
else
  warn "installing Claude Code…"
  curl -fsSL https://claude.ai/install.sh | bash >>"$LOG" 2>&1 || warn "Claude Code installer reported an issue (see $LOG)"
fi
# Make sure it's on PATH for the rest of this run.
for d in "$HOME/.local/bin" "$HOME/.claude/bin" "$BREW/bin"; do
  [ -d "$d" ] && case ":$PATH:" in *":$d:"*) ;; *) PATH="$d:$PATH" ;; esac
done
hash -r
if command -v claude >/dev/null 2>&1; then ok "claude on PATH ($(command -v claude))"; else warn "claude not on PATH yet — a new Terminal window will pick it up"; fi

# ─── 7. Choose where the studio lives ────────────────────────────────────────
step "Studio location"
[ -n "$STUDIO_DIR" ] || STUDIO_DIR="$(ask "Where should the studio live?" "$DEFAULT_DIR")"
# Expand a leading ~
case "$STUDIO_DIR" in "~"*) STUDIO_DIR="${HOME}${STUDIO_DIR#\~}" ;; esac
ok "$STUDIO_DIR"

# ─── 8. Fetch the studio ─────────────────────────────────────────────────────
step "Laying down the studio"
SELF_SRC="${BASH_SOURCE[0]:-$0}"
LOCAL_KIT=""
if [ -f "$SELF_SRC" ]; then
  SELF_DIR="$(cd "$(dirname "$SELF_SRC")" && pwd)"
  [ -f "$SELF_DIR/CLAUDE.md" ] && [ -d "$SELF_DIR/library" ] && LOCAL_KIT="$SELF_DIR"
fi

if [ -f "$STUDIO_DIR/CLAUDE.md" ]; then
  ok "studio already present — refreshing in place"
elif [ -n "$LOCAL_KIT" ]; then
  mkdir -p "$STUDIO_DIR"
  rsync -a --exclude '.git' --exclude 'library/catalog.db' "$LOCAL_KIT"/ "$STUDIO_DIR"/ >>"$LOG" 2>&1
  ok "copied from local checkout"
else
  TMP="$(mktemp -d)"
  say "  downloading from $TARBALL_URL"
  if curl -fsSL "$TARBALL_URL" | tar -xz -C "$TMP" >>"$LOG" 2>&1; then
    SRC="$(find "$TMP" -maxdepth 1 -type d -name "${REPO_NAME}*" | head -1)"
    [ -n "$SRC" ] || die "Could not unpack the download (see $LOG)."
    mkdir -p "$STUDIO_DIR"
    rsync -a --exclude '.git' "$SRC"/ "$STUDIO_DIR"/ >>"$LOG" 2>&1
    rm -rf "$TMP"
    ok "downloaded and unpacked"
  else
    die "Download failed. Check the repo owner (--owner) and your connection (see $LOG)."
  fi
fi

cd "$STUDIO_DIR" || die "Cannot enter $STUDIO_DIR"
chmod +x studio.sh tooling/*.sh tooling/catalog.py tooling/templates/*.sh 2>/dev/null || true

# Create the live credential drop box from the shipped template (git-ignored, so it isn't
# in the download). Never overwrite an existing one.
[ -f CREDENTIALS.txt ] || { [ -f CREDENTIALS.txt.template ] && cp CREDENTIALS.txt.template CREDENTIALS.txt; }

# ─── 9. Make it a git repo (the operator's own) ──────────────────────────────
step "Version control"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ok "already a git repo"
else
  git init -b main >>"$LOG" 2>&1 || git init >>"$LOG" 2>&1
  ok "initialized a local repo"
fi

# ─── 10. Build the knowledge catalog ─────────────────────────────────────────
step "Building the knowledge catalog"
if python3 tooling/catalog.py build >>"$LOG" 2>&1; then
  ok "$(python3 tooling/catalog.py categories 2>/dev/null | tr '\n' ' ' || echo 'built')"
else
  warn "catalog build reported an issue (see $LOG) — you can rebuild later with: python3 tooling/catalog.py build"
fi

# ─── 11. Optional private GitHub backup (the operator's own account) ──────────
step "Private cloud backup (optional)"
if [ "$NO_BACKUP" = "1" ]; then
  warn "skipped (--no-backup). Your work still saves locally."
  tooling/save.sh "Initial studio" >>"$LOG" 2>&1 || true
elif confirm "Back up your work to a private GitHub repo on your own account?"; then
  if ! gh auth status >/dev/null 2>&1; then
    say "  Opening GitHub sign-in (one-time)…"
    gh auth login || warn "GitHub sign-in didn't complete — saving locally for now"
  fi
  tooling/save.sh "Initial studio" >>"$LOG" 2>&1 || true
  if gh auth status >/dev/null 2>&1 && ! git remote get-url origin >/dev/null 2>&1; then
    if gh repo create "$REPO_NAME" --private --source=. --remote=origin --push >>"$LOG" 2>&1; then
      ok "private backup repo created and pushed"
    else
      warn "couldn't create the backup repo automatically (it may already exist). Your work is saved locally; see guides/04_git_and_backup.md"
    fi
  fi
else
  warn "no cloud backup — your work still saves locally"
  tooling/save.sh "Initial studio" >>"$LOG" 2>&1 || true
fi

# ─── 12. Done — hand off to login ────────────────────────────────────────────
step "All set"
cat <<EOF

  ${GREEN}${BOLD}Claude WP Studio is installed.${RESET}

  Your studio:   ${BOLD}$STUDIO_DIR${RESET}

  To start (and log in to Claude the first time):

      ${BOLD}cd "$STUDIO_DIR" && ./studio.sh${RESET}

  On first launch Claude will:
    • ask you to log in (your Claude subscription or an API key), then
    • set up the rest of the studio itself — just say: ${BOLD}Read START_HERE.md and follow it.${RESET}

  Day to day: open the folder, run ${BOLD}./studio.sh${RESET}, and tell Claude what you'd like to do.
  New here? Read ${BOLD}GETTING_STARTED.md${RESET}.

EOF

# Offer to launch straight into login if we have a real terminal.
if [ "$UNATTENDED" != "1" ] && [ -r /dev/tty ] && command -v claude >/dev/null 2>&1; then
  if confirm "Launch the studio now to log in?"; then
    exec ./studio.sh
  fi
fi
