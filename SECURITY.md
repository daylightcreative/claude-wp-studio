# Security

Claude WP Studio lets an AI work on live websites with little supervision. This page says
plainly what protects you, and where those protections stop.

## What Claude is allowed to do

The launcher (`studio.sh`) starts Claude Code in **auto mode**. Claude doesn't ask before each
step; instead a separate safety classifier reviews every action before it runs. It blocks
actions that are risky or out of scope, and ones that can't be undone, until you confirm them.
The studio tells the classifier:
- `wpsite` is the sanctioned route to your sites;
- deleting content, users, plugins or themes, database imports and resets, search-replace and DNS
  changes need your explicit go-ahead.

Auto mode isn't a guarantee: Anthropic documents it as a safety net, not a sandbox. If auto mode
isn't available on your account, Claude Code starts in its normal mode and asks you before
actions instead.

## Rules the tools enforce

These hold whatever Claude decides. Each is covered by the test suite:

| Rule | Enforced by |
|---|---|
| No change to a site without a verified database backup of that environment from the last 2 hours | `wpsite` (fails closed: any command not known to be read-only counts as a change) |
| PHP is syntax-checked by the server's own PHP before it can be loaded | `wpsite deploy` (uploads to a private folder outside the website, checks, then renames into place) |
| The previous version of anything replaced is kept | `wpsite deploy` |
| Folders shared with other things (`wp-content/plugins`, `themes`, `uploads` and the like) can't be replaced wholesale | `wpsite deploy` |
| Database passwords and WordPress keys and salts are hidden in output; `wp config get DB_PASSWORD` is refused | `wpsite` |
| Raw `ssh`, `scp`, `sftp` and `rsync` to a server are refused | the plugin's Bash hook |
| Claude can't read `CREDENTIALS.txt` or any `.secrets/` folder | permission deny rules (file tools and the file commands Claude Code recognises) plus the Bash hook |
| Nothing secret reaches git or your GitHub backup | `.gitignore`, plus a scan before every commit (also run as a git pre-commit hook). It refuses any value the studio holds for a site, private keys, wp-config secrets, common API-token formats, database dumps, and files too big for GitHub |

**Where these stop.** The Bash hook reads command text. A program Claude writes during a session
(a Python script that opens a network connection itself, say) isn't something it can see. That
case is left to the auto-mode classifier, which reviews what the program does. The backup rule
needs the backup to be *fresh*. It doesn't check that the backup covers the specific change, and
it doesn't restore anything for you.

## Where your passwords go

1. You type a site's login into `CREDENTIALS.txt` in your studio folder.
2. `wpsite secrets file <site>` reads it and writes the details to
   `projects/<site>/.secrets/<env>.env` (permissions `600`, inside a `700` folder). It then resets
   the drop box to blank. What it prints names the fields it filed, never their values.
3. When `wpsite` connects, it hands the SSH password to `ssh` through `SSH_ASKPASS`, a helper that
   reads it from the environment. The password never appears on a command line, in a terminal
   prompt or in the conversation.

Claude doesn't see the password at any point in this flow, so it doesn't reach Anthropic or your
Claude Code transcripts. If you paste a password into the chat instead, it does both. Use the
drop box.

**Prefer keys.** `wpsite key <site>` sets up SSH key login. Where the host manages keys in its
dashboard, it prints the public key for you to add there.

## What gets installed

- Homebrew (if missing), Node, the GitHub CLI and ImageMagick.
- Claude Code (Anthropic's native installer).
- The wp-studio plugin, from this repository's marketplace. Third-party plugins can run code on
  your Mac with your permissions; this one runs the Python in `plugin/` (standard library only)
  and the pinned Playwright MCP server (`@playwright/mcp`, exact version in `plugin/.mcp.json`).
- The Chrome-for-Testing browser that Playwright uses (headless, separate from your own browser).

## Backups

Your studio is a git repository. `studio save` (and the end of every session) commits locally,
then pushes to the GitHub repository you linked, if any. The push runs in the background. If it
fails, the next session tells you. Database dumps stay on your Mac in `projects/<site>/backups/`;
they aren't pushed.

## Reporting a vulnerability

Please report security problems in the kit privately through
[GitHub's private vulnerability reporting](https://github.com/daylightcreative/claude-wp-studio/security/advisories/new),
not in a public issue.
