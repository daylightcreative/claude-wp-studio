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
| No change to a site, including a deploy, without a verified database backup of that environment from the last 2 hours | `wpsite`. It fails closed: a WP-CLI command, flag or shell program not known to be read-only counts as a change |
| PHP is syntax-checked by the server's own PHP before it can be loaded | `wpsite deploy` (uploads to a private folder outside the website, checks, then renames into place) |
| The previous version of anything replaced is kept | `wpsite deploy` |
| Folders shared with other things (`wp-content/plugins`, `themes`, `uploads` and the like) can't be replaced wholesale | `wpsite deploy` |
| The site's database password, keys and salts, and anything secret in its connection details, are masked wherever they appear in output | `wpsite` (it learns the actual values from `wp-config.php` and masks them by value, not by guessing the output's shape) |
| Raw `ssh`, `scp`, `sftp` and `rsync` to a server are refused, wherever they sit in a command line | the plugin's Bash hook |
| Claude's file tools can't open the drop box, the secrets store or `~/.ssh`, and shell commands that name them (globs included) are refused | permission deny rules plus the Bash hook |
| The read-only agents (`site-scout`, `qa-checker`, `page-converter`) can't run a `wpsite` command that changes a site | the Bash hook |
| Nothing secret reaches git or your GitHub backup | `.gitignore`, plus a scan before every commit (also run as a git pre-commit hook). It refuses any value the studio holds for a site, private keys, wp-config secrets, common API-token formats, database dumps, and files too big for GitHub |

**Where these stop.**
- The Bash hook reads command text. It can't see a program Claude writes during a session (a
  Python script that opens a connection or a file itself), or a command assembled from variables at
  run time. The auto-mode classifier is the layer for those.
- The secrets store lives outside the studio folder, so a search inside the studio can't come
  across it. A search of your whole home folder could; that is a classifier matter too.
- The drop box is inside the studio folder while it holds something. Tell Claude as soon as
  you've filled it, so it gets filed and cleared.
- The backup rule needs a backup that is *fresh*. It doesn't check that the backup covers the
  specific change, and it doesn't restore anything for you.

## Where your passwords go

1. You type a site's login into `CREDENTIALS.txt` in your studio folder.
2. `wpsite secrets file <site>` reads it and writes the details to the secrets store,
   `~/.config/wp-studio/secrets/<studio id>/<site>/<env>.env`. The store is outside the studio
   folder, the file is `600` and the folders `700`. It then resets the drop box to blank. What it
   prints names the fields it filed, never their values.
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
- The Chrome for Testing build that the pinned Playwright MCP expects (headless, separate from your own
  Chrome, which the studio doesn't use).

## Backups

Your studio is a git repository. `studio save` (and the end of every session) commits locally,
then pushes to the GitHub repository you linked, if any. The push runs in the background. If it
fails, the next session tells you. Database dumps stay on your Mac in `projects/<site>/backups/`;
they aren't pushed.

## Reporting a vulnerability

Please report security problems in the kit privately through
[GitHub's private vulnerability reporting](https://github.com/daylightcreative/claude-wp-studio/security/advisories/new),
not in a public issue.
