---
name: debugging
description: Diagnose WordPress problems on a client site — a mystery tag or script in <head> no one can find, code hidden in snippet plugins, "every link redirects to one page", white screens and "critical error" fatals, and CLI-vs-web PHP mismatches. Use when the operator reports something on the site that shouldn't be there, a page that won't load, a redirect they can't explain, or a tracking script that fires from nowhere.
---

# Debugging a WordPress site

**Reproduce first, read before you write, and name the cause before you fix it.** Get one
command (a `curl`, a `wpsite wp` read, a browser check) that shows the exact symptom, run it, and
keep it: it is also how you prove the fix. Read-only investigation comes first. **Before any
invasive diagnostic** — switching on debug logging, deactivating a plugin, running a diagnostic
script, malware scanning, any `wpsite sh` command not on the read-only list — take a fresh
database backup:

```bash
wpsite backup acme
```

Use staging for anything that changes state when staging exists and shows the problem.

**Rule out the cache before anything else.** Purge (`wpsite purge acme`) and fetch with a unique
query string (`?cb=$RANDOM`). A page cache can serve a clean-looking or broken-looking copy long
after the stored page changed.

## 1. A tag or script in `<head>` that belongs to nothing

The usual hiding places are not theme files: they are the database rows of a snippet or
header-code plugin, a theme's options, or a string built from variables that no grep will match.
**Don't keep grepping — ask the site which callback prints it.**

**Step 1 — confirm it renders now:**

```bash
curl -s "https://www.example.com/about/?cb=$RANDOM" | grep -i 'og:image'
```

**Step 2 — search the database, including plugin tables.** `wp db search` only searches tables
WordPress registers unless told otherwise:

```bash
wpsite wp acme db search 'googletagmanager' --all-tables-with-prefix --stats
```

**Step 3 — check the known code stores.** Each of these keeps its code in the database, so a file
search finds nothing:

| Plugin / theme (version checked) | Where the code lives | Read it with |
|---|---|---|
| WPCode, formerly Insert Headers and Footers (2.4.0) | Global header/body/footer: options `ihaf_insert_header`, `ihaf_insert_body`, `ihaf_insert_footer`. Individual snippets: posts of type `wpcode` | `wpsite wp acme option get ihaf_insert_header` · `wpsite wp acme post list --post_type=wpcode --post_status=any --fields=ID,post_title,post_status` |
| Header Footer Code Manager (1.1.46) | Its own table, `<prefix>hfcm_scripts` | `wpsite wp acme db query "SELECT * FROM wp_hfcm_scripts"` (use the site's table prefix) |
| Code Snippets (4.0.0) | Its own table, `<prefix>snippets` (multisite network snippets: `ms_snippets`) | `wpsite wp acme db query "SELECT id,name,scope,active,code FROM wp_snippets"` |
| Divi theme options, "Integration" tab | Option `et_divi`, keys `divi_integration_head` and `divi_integration_body` (seen on a live Divi 4 site; current Divi **UNVERIFIED**) | `wpsite wp acme option pluck et_divi divi_integration_head` |

Find the site's table prefix with `wpsite wp acme db prefix`.

**Step 4 — attribute it.** If it is still unexplained, run `head-attribution.php` from this skill
folder. It simulates a request for one page, runs every `wp_head` callback on its own, and prints
each one whose output contains your text, with its priority and the file that defines it:

```bash
wpsite wp acme --input ${CLAUDE_SKILL_DIR}/head-attribution.php eval-file - 'og:image' about        # page path
wpsite wp acme --input ${CLAUDE_SKILL_DIR}/head-attribution.php eval-file - 'googletagmanager' 42   # post ID
wpsite wp acme --input ${CLAUDE_SKILL_DIR}/head-attribution.php eval-file - 'og:'                   # front page
```

It runs each callback's code, so take the backup above first and prefer staging. Tested on
WordPress 7.1.3 with WP-CLI 2.12.0. On a real site this named a header-code plugin's snippet in
one run, after a whole-webroot grep and a search of posts, postmeta and options had found nothing —
and showed two plugins each printing a full set of Open Graph tags with different values. If it
reports nothing, the tag comes from the theme's header template, a later hook, or JavaScript
(check the browser's DOM against the raw HTML from curl).

**Before assuming malware, look for a plugin with a private table.** If the source is a file no
installed plugin or theme owns, stop and switch to the `malware-response` skill.

**Removing it.** Save the current value to the project first (`wpsite backup acme --post <ID>` for a
snippet post, or the option's value into `work/`), then clear it with the plugin's own screen or
the matching `option update`. A tag that fires *inside* a Google Tag Manager container is removed in
Tag Manager, not WordPress.

## 2. "Every link redirects to one page"

**Ask one question first: does typing the same URL straight into the address bar work?**

- **Typed URL works, clicking fails → client-side JavaScript** is intercepting clicks. A server
  redirect can't tell a click from a typed URL, so the server is cleared. Look for injected script
  in the theme, a plugin, an injected core file, or `<script>` stored in content:
  `wpsite wp acme db search '<script' wp_posts --stats`.
- **Typed URL fails too → server-side.** Suspects, all readable without changes:
  `wpsite wp acme option get home` and `siteurl`; `show_on_front`, `page_on_front`,
  `page_for_posts`; `wpsite wp acme rewrite list`; a redirect plugin's wildcard rule (check its
  settings screen); and the server rules (`wpsite pull acme .htaccess` on Apache; on Nginx hosts
  `.htaccess` is ignored and the rules live in the host's panel).
- **The third case mimics both: a redirect that fires only for some visitors** — logged out, from
  a search engine, or on mobile. That is a common malware behaviour, and it is why the owner often
  can't reproduce it. Always test all three:

```bash
curl -sI "https://www.example.com/about/?cb=$RANDOM" | grep -i '^location'
curl -sI -e 'https://www.google.com/' "https://www.example.com/about/?cb=$RANDOM" | grep -i '^location'
curl -sI -A 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)' "https://www.example.com/about/?cb=$RANDOM" | grep -i '^location'
```

**"Re-save your permalinks" is not a fix.** Flushing rewrite rules often makes the symptom vanish
for a while, which says nothing about what corrupted them. If something is rewriting them, it comes
back. On a site with a history of infection, a disappearing symptom is evidence of nothing. A
conditional redirect you can reproduce goes to the `malware-response` skill.

## 3. White screen, "critical error", or a fatal

**Step 1 — scope it.** Fetch the home page, one inner page and `/wp-admin/` with
`curl -s -o /dev/null -w '%{http_code}\n'`. Then try `wpsite wp acme core version`.

- **WP-CLI works, the web fails** → something that loads only on web requests: a plugin's
  front-end code, the theme, or a **different PHP version**. The CLI's PHP is not necessarily the
  web PHP: on two managed hosts the CLI ran a newer PHP than the site. Compare `wpsite wp acme cli
  info` with the host dashboard or wp-admin → Tools → Site Health → Info → Server (the
  `site-access` skill has the detail).
- **WP-CLI fails too** → `wp-config.php` or a must-use plugin is fatal for every request. Try
  `wpsite wp acme plugin list --skip-plugins --skip-themes` to see whether WordPress loads without
  them.

"There has been a critical error on this website" means WordPress caught the fatal; it emails the
admin address a recovery-mode link.

**Step 2 — log the error, safely.** Per the official debugging guide
(developer.wordpress.org/advanced-administration/debug/debug-wordpress/): `WP_DEBUG_LOG` does
nothing unless `WP_DEBUG` is true; `true` writes `wp-content/debug.log`, or give it a file path;
`WP_DEBUG_DISPLAY` false hides errors from visitors; and the guide advises against debug tools on a
live site. `wp-content/debug.log` sits inside the web root, so it may be downloadable by URL — prefer
a path outside the web root that PHP can write to (which paths are writable is host-specific).

```bash
wpsite backup acme
wpsite wp acme config get WP_DEBUG                       # note the old value; empty output = false
wpsite wp acme config set WP_DEBUG_DISPLAY false --raw   # booleans take --raw
wpsite wp acme config set WP_DEBUG_LOG '/path/outside/webroot/wp-debug.log'   # a string: NO --raw
wpsite wp acme config set WP_DEBUG true --raw
```

Reproduce the failure once (cache-busted), then read the end of the log:
`wpsite sh acme 'tail -n 60 /path/outside/webroot/wp-debug.log'`. The first `PHP Fatal error`
line names the file and line.

**Turn it all off in the same session**, then delete the log file:

```bash
wpsite wp acme config delete WP_DEBUG_LOG
wpsite wp acme config delete WP_DEBUG_DISPLAY
wpsite wp acme config set WP_DEBUG false --raw           # or the old value you noted
```

**Never pass `--raw` with a string value.** `wp config set WP_AUTO_UPDATE_CORE minor --raw` wrote
`define('WP_AUTO_UPDATE_CORE', minor);`, an undefined constant, which took down the site *and*
WP-CLI, so WP-CLI couldn't repair it. The repair was a targeted `sed` on that one line (through
`wpsite sh`, with a backup). **Never print, pull or copy all of `wp-config.php`**: it holds the
database password and salts. Read only the line you need, e.g.
`wpsite sh acme 'grep -n "WP_AUTO_UPDATE_CORE" wp-config.php'`.

**Step 3 — isolate.** Once the log names a plugin or theme file, deactivate that one item on
staging and re-test. On live, only with the operator's go-ahead and after the backup. If the
backup itself fails because the site is down, stop and tell the operator: the host's dashboard
backup is the fallback.

## 4. "The fix is deployed but nothing changed"

Check in this order (the `caching` skill owns the cache layers): page cache (purge, then `?cb=`); browser cache on the operator's side (a
hard reload); a stored-content fact read from the database rather than the page
(`wpsite wp acme post get <ID> --field=post_content`); Divi's per-post CSS cache in
`wp-content/et-cache/<post-id>/`, which a content edit run with `--skip-themes` doesn't clear
(see the `divi` skill); and, for a PHP security patch, whether the web PHP workers
restarted after the new build (host-specific; ask the host if you can't see the processes).

## Report

Tell the operator, in plain words: what was wrong (one sentence), how you know (the command that
showed it before and after), what you changed, and where the backup is. Add a dated line to
`clients/<slug>.md`, and a one-line gotcha to `projects/<slug>/CLAUDE.md` if it could happen again.
