# WordPress Safety: Discover, Back Up, Stage, Confirm

**Date**: 2026-06-15
**Status**: Active
**Scope**: The non-negotiable safety habits for working on a live client WordPress site. Read this before touching any site.

These are the habits that keep a client's live site safe while you work fast from the
command line. They cost seconds and save disasters.

## 1. Discover before you touch

Never assume — read the real state of the site first.

```bash
./wp.sh core version
./wp.sh theme list            # which theme is active
./wp.sh plugin list           # what's installed/active
./wp.sh post list --post_type=page --fields=ID,post_title,post_status
./wp.sh post get <ID> --field=content   # the actual stored markup of a page
```

When matching or rebuilding something, **read what's actually there and reproduce it
exactly. Do not invent content, fields, options, or structure.** (On the Lindale dentists
site, forms were rebuilt by reading the live HTML field-by-field before cutover — nothing
was made up.)

## 2. Back up before every change

Before editing a page, theme file, or the database, save a timestamped copy into the
project's `backups/` folder.

```bash
# back up a page's content before editing it
./wp.sh post get <ID> --field=content > backups/page-<ID>-$(date +%Y%m%d-%H%M%S).html

# back up the whole database before structural work
./db-pull.sh
```

## 3. Work on staging or a local copy — not live

Build, convert, and experiment on a **staging site** (most hosts, including Kinsta, give
you one-click staging) or a local clone. Only touch the live site for small, confirmed
edits or the final, approved cutover. Always tell the user which one you're on.

## 4. Confirm anything irreversible or public

Deleting content, removing a plugin/theme, changing DNS, or anything visitors will see →
describe it plainly and get the user's OK first.

## 5. Editing content via WP-CLI safely

```bash
# pipe new content in over stdin (back up first!). On sites where complex markup gets
# stripped by KSES, run as an admin user with unfiltered_html:
./wp.sh post update <ID> - --user=<admin_login> --skip-plugins --skip-themes < backups/new-content.html
```

- **`--skip-plugins --skip-themes`** avoids a plugin/theme hook mangling the save.
- **`--user=<admin>`** gives `unfiltered_html` so complex block JSON / script tags aren't
  stripped (KSES otherwise rewrites them).

## 6. REST API needs an Application Password

If you use the WP REST API instead of WP-CLI, the **normal login password does not work**.
Create an **Application Password** (wp-admin → Users → your user → Application Passwords)
and Basic-auth with that. Whether script/complex markup can be saved depends on the user
having `unfiltered_html`.

## 7. Batch your SSH commands

SSH connections can get rate-limited. When you have several things to run, combine them
into one SSH session (one `wp.sh` call chaining commands, or a single remote script) rather
than many rapid separate connections.

## 8. Lint PHP before deploying

Any PHP you upload (theme file, mu-plugin) — run `php -l file.php` first. **A single syntax
error in an mu-plugin or active theme file fatals the entire site.** See
[custom CSS belongs in an mu-plugin](custom_css_belongs_in_mu_plugin.md).

## 9. Purge cache after changes

If a change "isn't showing," suspect stale cache before suspecting your change. Caching
behavior differs by host — see [caching by host](caching_by_host.md).
