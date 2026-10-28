#!/usr/bin/env bash
#
#   Claude WP Studio — installer (macOS)
#   https://github.com/daylightcreative/claude-wp-studio
#
#       curl -fsSL https://get.daylightcreative.tech/wp-studio | bash
#
#   What it does:
#     1. Installs what the studio needs: Apple's Command Line Tools, Homebrew, Node, the GitHub CLI,
#        ImageMagick and Claude Code. (Nothing WordPress-specific runs on the Mac: WP-CLI runs on
#        your web host.)
#     2. Creates your studio folder (or upgrades an existing one, including a v1 studio).
#     3. Installs the wp-studio plugin into it, plus the browser the studio uses to look at pages.
#     4. Optionally links a private GitHub repository on your own account as the backup.
#
#   Options:
#     --dir <path>        where the studio lives (default: ~/claude-wp-studio)
#     --no-backup         skip the GitHub backup step
#     --unattended        ask nothing (no backup unless one is already linked; needs sudo
#                         already authorized if Homebrew isn't installed yet)
#     --source <src>      plugin marketplace: owner/repo on GitHub (default) or a local folder
#
set -euo pipefail

usage() {
  cat <<'EOF'
Claude WP Studio installer (macOS)

  curl -fsSL https://get.daylightcreative.tech/wp-studio | bash
  curl -fsSL https://get.daylightcreative.tech/wp-studio | bash -s -- [options]

Options:
  --dir <path>     where the studio lives (default: ~/claude-wp-studio)
  --no-backup      skip the GitHub backup step
  --unattended     ask nothing: no backup unless already linked; needs sudo already
                   authorized if Homebrew isn't installed yet
  --source <src>   plugin marketplace: owner/repo on GitHub (default) or a local folder
EOF
}

SOURCE="${CLAUDE_WP_STUDIO_SOURCE:-daylightcreative/claude-wp-studio}"
STUDIO_DIR="${CLAUDE_WP_STUDIO_DIR:-}"
DEFAULT_DIR="$HOME/claude-wp-studio"
UNATTENDED=0
NO_BACKUP=0
LOG="$HOME/.claude-wp-studio-install.log"

while [ $# -gt 0 ]; do
  case "$1" in
    --unattended) UNATTENDED=1 ;;
    --no-backup)  NO_BACKUP=1 ;;
    --dir)        STUDIO_DIR="${2:?--dir needs a path}"; shift ;;
    --source)     SOURCE="${2:?--source needs a value}"; shift ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)"; exit 2 ;;
  esac
  shift
done

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
: > "$LOG"
log()  { printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
step() { printf '\n%s▸ %s%s\n' "$BOLD" "$*" "$RESET"; log "STEP $*"; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$*"; log "ok $*"; }
warn() { printf '  %s!%s %s\n' "$YELLOW" "$RESET" "$*"; log "warn $*"; }
die()  { printf '\n%sInstall stopped:%s %s\n  Details: %s\n' "$RED" "$RESET" "$*" "$LOG"; log "die $*"; exit 1; }
run()  { log "run $*"; "$@" >> "$LOG" 2>&1; }

interactive() { [ "$UNATTENDED" = 0 ] && [ -r /dev/tty ]; }
ask() { # ask "Question" "default"
  local answer=""
  if ! interactive; then printf '%s' "$2"; return; fi
  printf '%s%s%s %s[%s]%s ' "$BOLD" "$1" "$RESET" "$DIM" "$2" "$RESET" > /dev/tty
  read -r answer < /dev/tty || answer=""
  printf '%s' "${answer:-$2}"
}
confirm() { case "$(ask "$1 (Y/n)" "Y")" in [nN]*) return 1 ;; *) return 0 ;; esac; }

printf '\n%sClaude WP Studio%s — install\n' "$BOLD" "$RESET"
printf '%sLog: %s%s\n' "$DIM" "$LOG" "$RESET"

# ── 1. This Mac ─────────────────────────────────────────────────────────────────────────────────
step "Checking this Mac"
[ "$(uname -s)" = "Darwin" ] || die "This installer supports macOS only."
[ "$(id -u)" != 0 ] || die "Run the installer as yourself, not with sudo."
ok "macOS $(sw_vers -productVersion) on $(uname -m)"

step "Apple Command Line Tools"
if xcode-select -p >/dev/null 2>&1; then
  ok "already installed"
else
  warn "a system dialog will appear: click Install, then wait for it to finish"
  xcode-select --install >/dev/null 2>&1 || true
  until xcode-select -p >/dev/null 2>&1; do sleep 10; done
  ok "installed"
fi

# ── 2. Homebrew ─────────────────────────────────────────────────────────────────────────────────
step "Homebrew"
for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  [ -x "$candidate" ] && BREW="$candidate" && break
done
if [ -z "${BREW:-}" ]; then
  # Homebrew needs an administrator password once, to create its folder. Its installer can't ask
  # for it when run unattended, so ask here and keep the authorization alive while it runs.
  if interactive; then
    echo "  Homebrew needs your Mac's password once (the one you log in with). Nothing is shown as you type."
    # shellcheck disable=SC2024  # the redirect is for sudo itself: it reads the password from the terminal
    sudo -v < /dev/tty || die "Homebrew needs an administrator account on this Mac."
  elif ! sudo -n true 2>/dev/null; then
    die "Homebrew isn't installed and --unattended can't ask for the administrator password. Run 'sudo -v' first, or install without --unattended."
  fi
  ( while sudo -n true 2>/dev/null; do sleep 50; kill -0 "$$" 2>/dev/null || exit; done ) &
  KEEPALIVE=$!
  NONINTERACTIVE=1 run /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
    || { kill "$KEEPALIVE" 2>/dev/null; die "Homebrew didn't install."; }
  kill "$KEEPALIVE" 2>/dev/null || true
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$candidate" ] && BREW="$candidate" && break
  done
  [ -n "${BREW:-}" ] || die "Homebrew isn't where it should be after installing."
fi
eval "$("$BREW" shellenv)"
# shellcheck disable=SC2016  # written literally: new shells evaluate it
grep -q 'brew shellenv' "$HOME/.zprofile" 2>/dev/null || printf '\neval "$(%s shellenv)"\n' "$BREW" >> "$HOME/.zprofile"
ok "$("$BREW" --version | head -1)"

step "Tools"
for formula in node gh imagemagick; do
  if ! brew list --formula "$formula" >/dev/null 2>&1; then
    run brew install "$formula" || die "Couldn't install $formula."
  fi
  ok "$formula"
done

# ── 3. Claude Code ──────────────────────────────────────────────────────────────────────────────
step "Claude Code"
export PATH="$HOME/.local/bin:$PATH"
# Claude Code's native installer puts `claude` in ~/.local/bin but doesn't add it to PATH.
# shellcheck disable=SC2016  # written literally: new shells expand it
grep -qs 'HOME/.local/bin' "$HOME/.zprofile" || printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.zprofile"
if command -v claude >/dev/null 2>&1; then
  run claude update || true
  ok "$(claude --version 2>/dev/null | head -1)"
else
  run bash -c "curl -fsSL https://claude.ai/install.sh | bash" || die "Claude Code didn't install."
  hash -r
  command -v claude >/dev/null 2>&1 || die "Claude Code installed but isn't on PATH. Open a new Terminal window and run the installer again."
  ok "$(claude --version 2>/dev/null | head -1)"
fi

# ── 4. The studio folder ────────────────────────────────────────────────────────────────────────
step "Your studio folder"
[ -n "$STUDIO_DIR" ] || STUDIO_DIR="$(ask "Where should the studio live?" "$DEFAULT_DIR")"
case "$STUDIO_DIR" in "~"*) STUDIO_DIR="$HOME${STUDIO_DIR#\~}" ;; esac
mkdir -p "$STUDIO_DIR"
STUDIO_DIR="$(cd "$STUDIO_DIR" && pwd)"
ok "$STUDIO_DIR"
cd "$STUDIO_DIR"
# The studio is its own repository, even inside another one (a dotfiles home folder, say).
if [ "$(git rev-parse --show-toplevel 2>/dev/null)" != "$STUDIO_DIR" ]; then
  run git init -b main || die "Couldn't create the studio's git repository."
fi

# ── 5. The plugin ───────────────────────────────────────────────────────────────────────────────
step "The wp-studio plugin"
if [ -d "$SOURCE" ]; then
  SOURCE="$(cd "$SOURCE" && pwd)"
  SCOPE=local      # a development checkout: keep its path out of the shared settings file
else
  SCOPE=project
fi
run claude plugin marketplace add "$SOURCE" --scope "$SCOPE" || die "Couldn't add the plugin marketplace ($SOURCE)."
run claude plugin marketplace update daylight || true
run claude plugin install wp-studio@daylight --scope "$SCOPE" || die "Couldn't install the wp-studio plugin."
# `install` succeeds without changing anything when an older version is already installed.
run claude plugin update wp-studio@daylight --scope "$SCOPE" || die "Couldn't update the wp-studio plugin."
PLUGIN_ROOT="$(claude plugin list --json 2>>"$LOG" | /usr/bin/python3 -c '
import json, sys
for p in json.load(sys.stdin):
    if p.get("id") == "wp-studio@daylight":
        print(p.get("readFromFolder") or p.get("installPath")); break
')"
if [ -z "$PLUGIN_ROOT" ] || [ ! -x "$PLUGIN_ROOT/bin/studio" ]; then
  die "The plugin installed, but its files weren't found."
fi
STUDIO=("/usr/bin/python3" "$PLUGIN_ROOT/bin/studio")
ok "wp-studio $("${STUDIO[@]}" --version | awk '{print $2}')"

if [ -f tooling/catalog.py ] && [ ! -f .wp-studio ]; then
  # Snapshot the v1 studio in git first, so every file is recoverable whatever the upgrade does.
  run git add -A || die "Couldn't save your v1 studio to git before upgrading, so nothing was changed."
  if ! git diff --cached --quiet; then
    run git commit -q -m "Before upgrading to Claude WP Studio v2" \
      || die "Couldn't save your v1 studio to git before upgrading, so nothing was changed."
  fi
fi
MIGRATION="$("${STUDIO[@]}" migrate-v1 "$STUDIO_DIR")" || die "Upgrading the v1 studio failed."
log "$MIGRATION"
if printf '%s\n' "$MIGRATION" | grep -q '^- '; then
  ok "upgraded your v1 studio; nothing of yours was deleted:"
  printf '%s\n' "$MIGRATION" | sed 's/^/      /'
fi
touch .wp-studio
run "${STUDIO[@]}" sync || die "Couldn't lay down the studio files."
ok "studio files in place"

# ── 6. The browser the studio looks at pages with ───────────────────────────────────────────────
step "Browser for checking pages"
MCP_VERSION="$("${STUDIO[@]}" mcp-version)" || die "Couldn't read the browser version from the plugin."
if run npx -y "@playwright/mcp@$MCP_VERSION" install-browser chrome-for-testing; then
  ok "installed (Playwright MCP $MCP_VERSION)"
else
  warn "the browser didn't download; Claude can retry later with: npx -y @playwright/mcp@$MCP_VERSION install-browser chrome-for-testing"
fi

# ── 7. Backup ───────────────────────────────────────────────────────────────────────────────────
step "Backup"
run "${STUDIO[@]}" save "Set up Claude WP Studio" || die "The first save failed."
if git remote get-url origin >/dev/null 2>&1; then
  ok "already backed up to $(git remote get-url origin)"
elif [ "$NO_BACKUP" = 1 ] || ! interactive || ! confirm "Back up your studio to a private GitHub repository on your own account?"; then
  warn "saving on this Mac only. To add a GitHub backup later, ask Claude: \"set up my GitHub backup\"."
else
  gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web < /dev/tty || true
  if gh auth status >/dev/null 2>&1; then
    gh auth setup-git >> "$LOG" 2>&1 || true
    if run gh repo create "$(basename "$STUDIO_DIR")" --private --source . --remote origin --push; then
      ok "backed up to a private repository on your GitHub account"
    else
      warn "couldn't create the repository (one with that name may exist). Ask Claude to finish the backup setup."
    fi
  else
    warn "GitHub sign-in didn't finish. Ask Claude to set up the backup later."
  fi
fi

# ── Done ────────────────────────────────────────────────────────────────────────────────────────
cat <<EOF

  ${GREEN}${BOLD}Claude WP Studio is ready.${RESET}

  Start it:   ${BOLD}cd "$STUDIO_DIR" && ./studio.sh${RESET}

  The first time, Claude Code asks you to log in and to trust the folder. Then just say what you
  want, for example: ${BOLD}"Set up my first site: acme.com, hosted on Kinsta."${RESET}

EOF
if interactive && confirm "Start the studio now?"; then
  exec ./studio.sh
fi
