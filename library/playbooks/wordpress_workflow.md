# Playbook: The WordPress Working Method

**Date**: 2026-06-15
**Status**: Active
**Scope**: How to work on a client WordPress site day to day — the tools, the order of operations, and how design decisions flow between the operator and Claude.

This is the everyday method for building and maintaining a client's WordPress site. It
favors the command line (fast, precise, repeatable) and keeps the operator in the
director's seat. Pair it with the safety lesson:
[discover, back up, stage, confirm](../lessons/wordpress_safety_and_backups.md).

## The division of labor

- **The operator (you, the user)** sets the direction: the look, the content intent, the
  priorities, and the yes/no on anything that goes live. They describe what they want in
  plain language and review the result (often a screenshot or a staging link).
- **Claude** does the build: inspects the site, edits content and code, runs WP-CLI,
  manages the database, optimizes images, and reports back in plain language. Claude
  proposes options and a recommendation when a real design decision comes up — the
  operator decides.

## The tools (in order of preference)

1. **WP-CLI over SSH** (`./wp.sh …`) — the primary tool. Inspect, edit content, manage
   plugins/themes/options, query the DB. No dashboard login needed.
2. **The local database/content pull** (`./db-pull.sh`, or `wp post get … --field=content`)
   — pull content down to read and transform offline, then push back. Essential for bulk
   work like a Divi→Gutenberg conversion.
3. **SFTP/scp** — for uploading theme files and mu-plugins.
4. **The WordPress dashboard / live site in a browser** — mainly to *verify visually* and
   to take screenshots for the operator. Also for the few host actions that aren't scriptable
   (e.g. MyKinsta cache clear, creating staging).
5. **A real browser (Playwright)** — to confirm how a page actually renders (desktop +
   mobile), catch JS/runtime issues, and screenshot before/after. "Works in my browser" is
   often just [stale cache](../lessons/caching_by_host.md).

## A typical task, start to finish

1. **Search the library** for prior lessons/decisions:
   `python3 tooling/catalog.py search "<topic>"`.
2. **Open the client doc** in `library/clients/<client>.md` for the stack, access, and
   gotchas. (If none exists yet, set the project up first — see
   [client project setup](client_project_setup.md).)
3. **Discover** the relevant current state with `./wp.sh …`.
4. **Decide where to work:** staging/local for anything substantial; live only for small
   confirmed edits.
5. **Back up** what you're about to change.
6. **Make the change** (content via WP-CLI; styling via an
   [mu-plugin](../lessons/custom_css_belongs_in_mu_plugin.md); structure via blocks).
7. **`php -l`** any PHP before uploading.
8. **Purge the right cache** for this host.
9. **Verify** in a real browser, desktop and mobile; screenshot for the operator.
10. **Record** anything learned: update the client doc's work log, write a new lesson if it
    was a gotcha, rebuild the catalog, and log a line in `../WORKLOG.md`.

## Design tokens, not scattered CSS

When building, capture the design as **tokens** — the palette, fonts, and spacing — in the
theme's `theme.json` (block themes) so the whole site stays consistent and editable. Reserve
hand-written CSS for the genuinely custom bits, and keep it in an mu-plugin or the theme's
stylesheet, scoped tightly.

## Keep the client doc current

Every client's `library/clients/<client>.md` is the source of truth for that site: stack,
where the secrets live, the correct cache-clear method, key decisions, and a dated work log.
Update it as you go — future sessions (and future-you) rely on it.
