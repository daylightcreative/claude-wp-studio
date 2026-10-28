---
name: safe-changes
description: The core habits for changing a live client WordPress site without breaking it — read the real state first, back up, prefer staging, confirm irreversible steps, edit content through WP-CLI safely, deploy code only with `wpsite deploy`, and prove the change is live. Use when about to edit content, options, CSS, theme or plugin files, wp-config, or the database on any site, or when checking whether a change worked.
---

# Safe changes to a live site

Every change follows the same loop: **discover → back up → change (staging first when it
matters) → verify what is live → tell the operator what changed.** Skipping a step is how a
two-minute edit becomes a client outage.

## 1. Discover before you touch

Read the real state of the site before deciding anything. Never invent content, field names,
option names or structure; read what is there and reproduce it exactly.

```bash
wpsite check acme                                   # WP version, home URL, visibility, host, cache layer, CLI PHP
wpsite wp acme theme list
wpsite wp acme plugin list
wpsite wp acme post list --post_type=page --fields=ID,post_title,post_status
wpsite wp acme post get 42 --field=post_content     # the stored markup, not the rendered page
```

- **A note is a claim, not a fact.** A doc, ticket or earlier session saying "done", "none
  exists" or "use these files" can be wrong. Re-check it against the site before acting on it.
- **Record how to look things up, not the values.** In the client's `CLAUDE.md`, write
  "versions: `wpsite wp acme core version`, `plugin list`, `theme list`", not "WordPress 6.x,
  Divi 4.x". Sites auto-update; a version written into a doc is wrong within weeks and the next
  session trusts it.

## 2. Back up first

`wpsite wp` refuses any command that can change the site, `wpsite sh` any command not on its
small read-only list, and `wpsite deploy` every upload, unless a database backup of that
environment less than 2 hours old exists (exit code 3). That gate is the floor,
not the plan. Back up deliberately before each change:

```bash
wpsite backup acme                      # verified gzip database dump
wpsite backup acme --post 42            # one post's stored content, before editing it
wpsite backup acme --file wp-config.php # a remote file, before changing it
```

Everything lands in `projects/acme/backups/<env>/`. Tell the operator where the backup is when
you report the change.

For a content rewrite the client may want undone, also keep the original on the post itself, so
the restore is one command and survives independent of local files:

```bash
wpsite wp acme eval 'update_post_meta(42, "_wpstudio_content_backup", get_post_field("post_content", 42));'
```

(A leading underscore keeps the meta key out of the Custom Fields box.)

## 3. Staging or live

Build, convert, update and experiment on staging (`acme:staging`). Touch live only for small,
confirmed edits or an approved cutover. **Say which environment you are on** every time you
report. Staging has its own hazards (pushes, indexing, outbound email) — see the
`wp-studio:staging` skill before using it.

## 4. Confirm anything irreversible or public

Before deleting content, users or media, removing a plugin or theme, changing DNS, sending
email, or changing anything visitors will see on live: describe it in plain words, say what the
backup is, and get the operator's yes. Plain version to the operator: *"I'm about to delete the
three old landing pages. I've saved copies. Once they're gone, links to them will 404. OK?"*

**What counts as a change.** `wpsite` treats anything it can't prove read-only as a change:
every `wp db query` (the mysql client can run commands from inside the SQL text), any WP-CLI flag
outside its known-safe list, and in `wpsite sh` any unquoted `$`, `*`, `{`, `~` or backslash (the
server's shell would expand them into text nobody checked). Quote search patterns, prefer
`wp db tables`, `wp db search` and the `wp post list` family for reading, and when you do need SQL,
take the backup first. A command that names `wp-config.php` may only read it with `grep`, `cat`,
`head` or `tail`; change it with `wp config set`.

## 5. Editing content through WP-CLI

Feed the new content in with `--input` (`-` makes WP-CLI read post content from standard input,
per the WP-CLI docs), and run as an administrator so WordPress's HTML filter (KSES) does not strip
markup:

```bash
wpsite backup acme --post 42
wpsite wp acme --input projects/acme/work/page-42.html post update 42 - --user=<admin_login>
```

- **Why `--user`:** with no user, WP-CLI runs as nobody, so the `unfiltered_html` capability is
  missing and KSES rewrites script tags, iframes and some block attributes. Administrators have
  `unfiltered_html` on a single site; on multisite only Super Admins do, and the
  `DISALLOW_UNFILTERED_HTML` constant removes it for everyone.
- **Do not add `--skip-plugins --skip-themes` by default.** It skips every `save_post`
  callback the theme and plugins registered. On Divi this is a real bug: Divi clears its
  per-post CSS (`wp-content/et-cache/<post-id>/`) from a theme callback on `save_post`, so a
  skipped-theme edit leaves the old CSS in place. Divi names its CSS rules by section *index*,
  so an edit that adds or removes a section makes every later rule land on the wrong section
  (verified on Divi 4.27). SEO and cache plugins that react to saves are skipped the same way.
- **When skipping is right:** read-only commands that a broken or noisy plugin is crashing, and
  recovery when a plugin fatal stops WP-CLI loading at all. If you did write with the theme
  skipped on a Divi site, finish the job:
  ```bash
  wpsite sh acme 'rm -rf wp-content/et-cache/42'   # Divi rebuilds it on the next view
  wpsite purge acme
  ```
  (`wpsite sh` and `wpsite wp` both start in the WordPress root, so paths are relative to it.)
  Then look at the page; this failure produces valid HTML that passes every text check.
- **Large or awkward values** (the Customizer's Additional CSS is often tens of KB): change them
  server-side in PHP rather than shell-escaping the blob. Write a small PHP file, deploy it to a
  scratch path or feed it on standard input (`wpsite wp acme --input FILE …`,
  `wpsite sh acme --input FILE '<cmd>'`), and make it idempotent with a marker string so a re-run does
  not append twice. Read with `wp_get_custom_css()`, write with `wp_update_custom_css_post()`.
- **Run PHP files with `wp eval-file --use-include`.** Without it, WP-CLI evaluates the file's
  contents with `?>` prepended; a file starting with `declare(strict_types=1);` then fatals
  (seen with WP-CLI 2.12 on PHP 8.4, while the same file ran on 8.5 — so it passed on staging
  and would have failed on live).
- **Never use `wp config set … --raw` for a string.** `--raw` writes the value unquoted.
  `wp config set WP_AUTO_UPDATE_CORE minor --raw` produced `define('WP_AUTO_UPDATE_CORE', minor);`
  — an undefined-constant fatal that took down the site *and* WP-CLI, so WP-CLI could not undo
  it. Use `--raw` only for `true`, `false`, numbers and real PHP expressions. Back up
  `wp-config.php` with `wpsite backup acme --file wp-config.php` first; if it does fatal,
  restore that file with `wpsite deploy`.
- **REST API instead of WP-CLI:** the account's normal password does not work; it needs an
  Application Password over Basic auth. The studio's `hardening.php` turns Application Passwords
  off by default, so on a hardened site the section is missing from the profile. Re-enable them
  only if the operator agrees something outside needs the REST API: set
  `WPSTUDIO_DISABLE_APP_PASSWORDS` to `false` (see `wp-studio:updates-and-hardening`), redeploy,
  then create one under Users → profile → Application Passwords. Whether rich markup survives
  still depends on that user having `unfiltered_html`.

## 6. Deploying code: only `wpsite deploy`

Theme files, plugins, mu-plugins and any PHP go up with `wpsite deploy`, never by pasting into
`wpsite sh`:

```bash
wpsite deploy acme:staging projects/acme/work/my-mu.php wp-content/mu-plugins/my-mu.php
```

It needs a fresh `wpsite backup` like any change. What it does, and why each step exists:

- **Uploads into a private staging folder in the SSH user's home**, outside the website, so
  unchecked code can never be requested over the web or loaded by WordPress. The transfer is a
  tar stream over the same SSH connection `wpsite` uses for everything (not rsync). If the upload
  dies part-way, nothing on the site has changed; deploy again, or in smaller parts.
- **Lints PHP there with the server's own PHP before it goes near the site.** One syntax error in
  an mu-plugin or active theme file takes down the whole site, and an mu-plugin cannot be
  deactivated from wp-admin. Run `php -l` locally too.
- **Saves the current version locally** (under `projects/<slug>/backups/<env>/files/`; a folder
  as a `.tar`), so a bad deploy is reversible.
- **Copies the new version beside the destination under a name WordPress never loads, then
  renames it into place**, so the site never runs a half-copied file or folder.
- **Resets PHP's opcode cache.** On managed hosts PHP-FPM kept serving the old compiled code
  for about a minute after an upload, and a new file calling a new method returned HTTP 500 in
  that window. WP-CLI cannot fix this: `opcache_reset()` only clears the cache of the PHP process
  that calls it, and the CLI's cache is separate from PHP-FPM's.
- **Verifies checksums**, so "uploaded" means "the server has exactly these bytes".

Deploy gotchas:

- **A folder deploy replaces the whole destination folder.** Files on the server that are not in
  your local copy are gone afterwards (the previous version is in the saved `.tar`). So deploy
  single files, or a complete local copy of the folder: `wpsite pull` it first, change it, deploy
  it back. The WordPress root and its shared folders (`wp-admin`, `wp-includes`, `wp-content` and
  its `plugins`, `themes`, `uploads`, `mu-plugins`, `languages`, `upgrade`) cannot be replaced
  wholesale; `wpsite` refuses, and you deploy into a subfolder such as
  `wp-content/themes/<theme>` or a single file instead.
- **Never delete a theme or plugin folder before deploying it.** The deploy already swaps the
  folder in one rename; deleting first leaves the site with no active theme if anything fails.
- **Block themes cache their pattern-file list.** A new file in `patterns/` stays invisible
  until the cache is cleared (`WP_Theme::delete_pattern_cache()`, WordPress 6.4+) — make it part of the deploy:
  `wpsite wp acme eval 'wp_get_theme()->delete_pattern_cache();'`
- **CLI PHP is not web PHP** on several managed hosts. `wpsite check` reports the CLI version;
  the site may run another. See the `wp-studio:site-access` skill before trusting a PHP version.
- **Version your own theme assets by file time** (`filemtime()` as the `$ver` of
  `wp_enqueue_style` / `wp_enqueue_script`) so every deploy changes the asset URL and no
  browser or CDN keeps the old file.

## 7. Verify what is live

"I deployed it" is not "it is live". Prove it from three directions:

1. **Purge, then bust.** `wpsite purge acme`, then fetch with a unique query string so every
   request is a cache miss: `curl -s "https://example.com/page/?cb=$RANDOM"`. Do the same for
   every browser navigation (`…?cb=<unique>`). Check more than the homepage, and grep for
   `fatal error|parse error`. Details by host: the `wp-studio:caching` skill.
2. **Read stored facts from the database, which has no page cache:**
   `wpsite wp acme post get 42 --field=post_content`, `wpsite wp acme option get blogname`.
   This tells you what is stored; the page tells you how it renders. You need both.
3. **Measure layout; do not judge it from a screenshot.** A downscaled screenshot of
   left-aligned text looks centered. For alignment, width, offset or overflow, read the DOM
   with the browser's `evaluate` tool:
   ```js
   [...document.querySelectorAll('main p')].slice(0, 20).map(p => {
     const r = p.getBoundingClientRect(), par = p.parentElement.getBoundingClientRect();
     return { align: getComputedStyle(p).textAlign, left: r.left - par.left,
              right: par.right - r.right, text: p.textContent.trim().slice(0, 40) };
   });
   // horizontal overflow: document.documentElement.scrollWidth > innerWidth
   ```

**When you do need a picture:** the Playwright MCP screenshot call has a hard 5-second limit
that cannot be raised, and pages with scroll-reveal animations or long bodies never finish in
time (full-page, viewport and element shots all fail; `evaluate`, `navigate` and `click` still
work). Use shot-scraper from Bash, which has no such cap:

```bash
shot-scraper "https://example.com/page/?cb=$RANDOM" -o projects/acme/work/page.png \
  --width 1440 --wait 2500 --reduced-motion \
  --javascript "document.head.insertAdjacentHTML('beforeend','<style>*{animation:none!important;transition:none!important}</style>')"
```

Full page is the default; add `--height 900` for one viewport, `--selector '.hero'` for one
element. Inspect sections of a tall shot at full resolution (crop it) instead of a thumbnail.

- **Third-party widgets may refuse automated browsers.** An embed behind Cloudflare bot
  protection returned 403 to curl and headless Chrome from every network while a normal Chrome
  window loaded it. If a widget is blank only in automation, ask the operator to check it in
  their own browser before calling it broken.
- **Client says "still broken" right after a fix:** usually their browser cache. Plain
  version: *"Please hold Shift and click reload."*

## 8. Report

Tell the operator: what changed, on which environment, where the backup is, how you verified it,
and anything you could not verify (for example, a cache layer `wpsite purge` said it could not
clear).
