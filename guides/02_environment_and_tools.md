# Guide 02 — Environment & Tools

**Audience:** Claude, during activation (and any time a tool seems missing).

This studio needs a handful of command-line tools. The one-line installer normally sets all of
them up. But **if a tool is missing, just install it yourself and move on** — you have bypass
permissions. Don't hand the operator install commands; don't stall for permission on routine
tooling.

## ⚠️ Use a modern Python — not macOS's system Python

macOS ships an **old, locked-down** Python that can break or refuse package installs. The
installer installs the **Homebrew Python 3** for exactly this reason. Verify you're on it:

```bash
python3 --version                 # should be a recent 3.x (Homebrew), not the system one
which python3                     # should be under /opt/homebrew or /usr/local, not /usr/bin
python3 -c "import sqlite3; print('sqlite3 OK')"   # the catalog needs this
```

If `python3` is the old system one or missing, install the Homebrew Python and proceed:

```bash
brew install python
```

## Verify what's installed

```bash
python3 --version          # knowledge-base catalog (required)
sqlite3 --version          # the catalog database engine (required)
git --version              # version control / backup (required)
ssh -V                     # remote access to sites (required for client work)
rsync --version | head -1  # file sync/upload (recommended)
curl --version | head -1   # HTTP checks, downloads (present on macOS)

wp --info 2>/dev/null || echo "WP-CLI: missing"        # the main WordPress tool
mysql --version 2>/dev/null || echo "mysql client: missing"
mysqldump --version 2>/dev/null || echo "mysqldump: missing"
magick --version 2>/dev/null | head -1 || echo "ImageMagick: missing"
gh --version 2>/dev/null | head -1 || echo "GitHub CLI: missing"
```

## What each tool is for

| Tool | Needed for | Required? |
|------|------------|-----------|
| **python3** (Homebrew) | Runs `catalog.py` (the searchable knowledge base) | Yes — for activation |
| **sqlite3** | The catalog's database (FTS5 full-text search) | Yes |
| **git** | Version-controlling the studio (the auto-save backup) | Yes |
| **ssh** | Reaching client sites to run WP-CLI, edit, upload | Yes — for client work |
| **rsync** | Efficient file uploads to servers | Recommended |
| **WP-CLI (`wp`)** | The authoritative way to inspect/edit WordPress over SSH. *Note:* often it only needs to exist **on the server** (most managed hosts, incl. Kinsta, have it) — `wp.sh` runs it remotely. A local `wp` is handy for local site copies. | For client work |
| **mysql / mysqldump** | Local database work and inspecting dumps. (`db-pull.sh` uses the server's `wp db export`, so a local client is only needed for local imports.) | When doing local DB work |
| **ImageMagick (`magick`)** | Optimizing images (the [recipe](../library/lessons/image_optimization.md)) | When building/migrating image-heavy pages |
| **gh** (GitHub CLI) | The optional private GitHub backup of the studio (`tooling/save.sh`) | For cloud backup |

## Installing what's missing (just do it)

With Homebrew present, the one-liners are:

```bash
brew install python            # modern Python 3 (do NOT rely on system python)
brew install wp-cli            # WP-CLI
brew install mysql-client      # mysql/mysqldump (client only)
brew install imagemagick       # magick
brew install gh                # GitHub CLI (backup)
brew install git rsync         # if somehow absent
```

If **Homebrew itself is missing**, install it (the official one-liner from brew.sh), then the
tools above. This is exactly the kind of setup you're authorized to do — don't make the
operator do it. If a step fails for a reason you can't fix (a permissions or network problem
on their Mac), explain it plainly and ask them for the one thing you need.

Don't block activation on the WordPress/image tools — install those when the first client task
needs them.

## A note on browsers (optional, very useful later)

For verifying how pages actually render (desktop + mobile) and catching JavaScript/runtime
issues, a real browser via Playwright is invaluable — "works in my browser" is often just
[stale cache](../library/lessons/caching_by_host.md). It's not needed for activation; set it
up when you first need visual verification on a client site.
