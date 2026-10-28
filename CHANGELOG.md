# Changelog

The plugin's version lives in `plugin/.claude-plugin/plugin.json`; the newest entry here must match
it (a test checks). Installed studios update when this version changes.

## 2.0.0 — 2026-10-28

A rebuild. The studio is now a Claude Code plugin plus a workspace folder, and the safety rules
are enforced by tools instead of written down as instructions.

**Safety**
- **Auto mode replaces bypass permissions.** `studio.sh` launches with `--permission-mode auto`,
  passing the studio's context to the safety classifier.
- **New `wpsite` command, the only route to a site:**
  - changes, deploys included, need a verified database backup less than 2 hours old. Anything
    not known to be read-only counts as a change, WP-CLI flags included (`--exec` and
    `--require` run code);
  - deploys check PHP with the server's own PHP, outside the website, before swapping it in
    atomically;
  - the previous version is kept;
  - PHP's opcode cache is reset with a single-use request;
  - uploads are checksum-verified;
  - the site's own database password, keys and salts are masked by value in all output;
  - logins are shared over one SSH connection (managed hosts throttle repeated logins).
- **Bash hook** refuses raw `ssh`/`scp`/`sftp`/`rsync` wherever they sit in a command line, any
  command that names the drop box, the secrets store or the studio's SSH key, and site-changing
  `wpsite` commands inside the read-only agents.
- **Claude no longer reads passwords.** `wpsite secrets file` files the drop box itself into a
  secrets store outside the studio folder (`~/.config/wp-studio`), and permission deny rules block
  Claude's file tools from both. v1 said passwords "never leave your computer" while Claude read
  them into the conversation; that is now true for the drop-box flow.
- **Secret scan before every commit** (save and git pre-commit hook), including the exact values
  the studio holds for each site.
- **Backups:** the end-of-session save pushes in the background, so Claude Code's 1.5-second
  SessionEnd budget no longer cuts it off. A failed push is reported at the next session.

**Fixes**
- **Browser:** the Playwright MCP is pinned, uses Playwright's own Chrome for Testing build (not
  your installed Chrome), and the installer downloads exactly that build. So page checks work on a
  fresh install. Before, `@latest` and a separately installed Chromium build disagreed.
- **Installer:**
  - on a Mac without Homebrew, it now asks for the administrator password Homebrew needs instead
    of failing silently;
  - re-running it updates the plugin and the studio (it used to print "refreshing" and change
    nothing);
  - `claude` is added to the PATH of new Terminal windows;
  - it no longer installs tools the studio doesn't use on the Mac (WP-CLI, mysql-client).
- **Password-only hosts:** these work, through SSH_ASKPASS; `wpsite key` sets up key login.
- **Requests to the website go through `curl`.** The Python that ships with Apple's Command Line Tools
  (LibreSSL 2.8) fails the TLS handshake with common CDNs, which silently broke the opcache reset after a
  deploy on a real Kinsta site.

**Knowledge**
- **Fifteen skills** replace the v1 library and its search catalog, rewritten from four more months
  of client work. They cover:
  - update policy and hardening (with mu-plugins), malware response (with a read-only detector),
    plugin audits;
  - staging hazards (with a guard mu-plugin), caching;
  - Divi, Divi to blocks with migration QA, block themes;
  - images, launch QA, debugging (with a head-tag attribution script), site access;
  - delegating big jobs.
- **Corrected v1 advice:**
  - "turn auto-updates off on production" is reversed: keep them on, hold back only page-builder
    majors;
  - `--skip-themes` content edits on Divi leave stale CSS;
  - "never use Additional CSS" was a Divi 5 finding, not a rule;
  - a changed SSH host key is now treated as a possible attack until the host confirms it.
- **Three agents:** `site-scout` and `qa-checker` (read-only) and `page-converter`.

**Upgrading:** run the installer on your v1 folder. It commits the studio first, then moves client
records to `clients/` and connection files to the secrets store. Anything you wrote or changed in
the old kit folders goes to `v1-kept/`, and your old `CLAUDE.md` becomes `CLAUDE.v1.md`. Only files
byte-identical to what v1 shipped are removed.

## 1.0.0 — 2026-06-17

First public release.
