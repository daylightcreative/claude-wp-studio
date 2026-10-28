---
name: updates-and-hardening
description: Keep a client WordPress site patched and hardened without anyone watching it. Covers automatic updates enforced in code (with a hold only for cross-major page-builder jumps), the update traps (paid/free plugin pairs, expired licences, premium updaters that never run unattended), application hardening, blocking PHP in uploads, and patching the server's PHP. Use when setting up or reviewing a site's update policy, when someone suggests turning auto-updates off, when a vulnerability notice names a plugin, theme or PHP version, when an update "did nothing", or after a malware cleanup.
---

# Updates and hardening

**Rule: automatic updates stay on for core, every plugin and every theme, enforced in code, and
nothing you add may block them.** The only exception is a cross-major upgrade of a page builder
(or a free plugin whose paid half is version-locked to it), which is held for a person to test on
staging. Hardening that stops a site from patching itself is negative security.

Older advice to "turn WordPress auto-update OFF on production" and pin the theme is wrong for an
unattended site. It trades a rare broken layout for months of known holes. Hold the one risky
major jump instead; let everything else update.

Why, from real sites:
- A dashboard "auto-updates on" setting is just a row in `wp_options`. On one site it had quietly
  drifted: two plugins (one of them the security plugin) were off, and nothing noticed.
- On another site, `DISALLOW_FILE_MODS` had been added during an earlier cleanup. It disables all
  automatic updates. Live sat for weeks on a form plugin with a CVSS 9.8 file-upload hole and got
  attacked through it; the staging copy, without the constant, had patched itself.

## Install the two must-use plugins

This folder ships two complete, `php -l`-clean files. Install both; each reports the other missing.

| File | Install as | Does |
|---|---|---|
| `update-policy.php` | `wp-content/mu-plugins/wpstudio-update-policy.php` | Forces updates; holds listed cross-major jumps; asserts the result |
| `hardening.php` | `wp-content/mu-plugins/wpstudio-hardening.php` | Hardening below; asserts it and that `DISALLOW_FILE_MODS` is off |

1. Copy both into `projects/<slug>/work/mu-plugins/` and set the configuration block at the top of
   each. Defaults suit a builder-free site reached only over SSH/WP-CLI. The settings you are most
   likely to change:
   - `WPSTUDIO_HOLD_MAJOR_THEMES`, e.g. `array( 'Divi' )`: the theme folder name of a page builder.
   - `WPSTUDIO_HOLD_MAJOR_PLUGINS`, e.g. `array( 'elementor/elementor.php' )`: plugin file.
   - `WPSTUDIO_DISABLE_APP_PASSWORDS`: see Hardening.
   - `WPSTUDIO_LOGIN_THROTTLE`: leave `0` if a security plugin already throttles logins.
2. Deploy (it lints on the server, backs up, resets opcache and verifies):
   ```
   wpsite backup acme
   wpsite deploy acme projects/acme/work/mu-plugins/wpstudio-update-policy.php wp-content/mu-plugins/wpstudio-update-policy.php
   wpsite deploy acme projects/acme/work/mu-plugins/wpstudio-hardening.php wp-content/mu-plugins/wpstudio-hardening.php
   ```
3. Prove it holds. Both lists must print empty:
   ```
   wpsite wp acme eval 'print_r( wpstudio_update_policy_failures() ); print_r( wpstudio_hardening_failures() );'
   ```
4. **Negative-test it.** A guardrail you have only seen pass is not a guardrail. Remove a filter in
   memory and confirm the exact failure appears:
   ```
   wpsite wp acme eval 'remove_all_filters( "auto_update_plugin" ); print_r( wpstudio_update_policy_failures() );'
   ```
   Expect "Plugin automatic updates are not forced on." Repeat on every environment.

How it works (verified in WordPress 6.9.1 source and on developer.wordpress.org): the
`auto_update_{$type}` filter gets `( $update, $item )`; `$item->plugin` is the plugin file,
`$item->theme` the theme folder, `$item->new_version` the offer. Core also calls it with
`$update === null` only to ask "is this forced?" (`wp_is_auto_update_forced_for_item()`); a
non-null answer removes the per-item toggle from the dashboard. Both files answer every call with
a real boolean. The assertions run the live filter chain ("are updates really forced?"), never
"is the line still there?", so they catch an edited file, a deleted file, or a plugin overriding
the filter. Failures show three ways: a critical Site Health item (Tools → Site Health), an error
notice on every admin screen for administrators, and the `eval` check above.

A held major upgrade on offer is also reported as a critical Site Health item, so a hold is a
decision and never a silent skip. Tell the operator: "Version N of the page builder is out. It's a
big rewrite, so it doesn't install itself. I'll test it on staging first."

## Update traps

**1. Free and paid plugin pairs are version-locked.** Several products ship a free plugin plus a
paid companion that declares which free version it needs. Updating the free half across a major
while the paid half stays behind breaks the paid features. Before an update pass, read what the
paid half expects, straight from its header:
```
wpsite sh acme 'grep -m8 -E "^ \* (Version|Requires|.*tested up to)" wp-content/plugins/<paid-plugin>/<main-file>.php'
wpsite wp acme plugin list --fields=name,version,update_version
```
If the paid half shows no `update_version`, do not move the free half across a major; add the
free plugin to `WPSTUDIO_HOLD_MAJOR_PLUGINS`. If it already moved, roll back with an explicit
version: `wpsite wp acme plugin update <free-slug> --version=<x.y.z>`.

**2. An expired licence looks like "up to date".** A blank `update_version` on every commercial
plugin means the licences are expired or not activated, not that the plugins are current. Check
production too: if production also shows no updates, it is a licensing problem and production is
getting no security fixes. That is a conversation with the operator, not something to fix in
WP-CLI. Licences are often activated for the production domain only, so staging reports "not
activated for this domain" and cannot download updates.

**3. Some premium updaters only check during a wp-admin page load.** Observed 2026-10 on a form
plugin's premium add-ons, whose Easy Digital Downloads Software Licensing-style updater injects its
offer into the `update_plugins` transient only when someone loads wp-admin. WP-Cron and WP-CLI
never see the update, so a CVSS 8.1 fix sat uninstalled while `wp plugin list` said "none". To
surface the offer from WP-CLI, run the admin hooks as an administrator (this changes the update
cache; take the backup first):
```
wpsite backup acme
wpsite wp acme eval 'wp_set_current_user( <admin-id> ); do_action( "admin_init" ); delete_site_transient( "update_plugins" ); wp_update_plugins();'
wpsite wp acme plugin list --fields=name,version,update_version
```
Then update on staging, check the forms still render the same fields, then live. Record which
plugins on the site work this way in the project's `CLAUDE.md`: the update policy cannot install
what WordPress never sees.

**4. WP-Cron runs only when someone visits.** A quiet staging site lags behind live because its
update checks sit overdue. Check with `wpsite wp acme:staging cron event list` and run what is due
with `wpsite wp acme:staging cron event run --due-now`.

**5. Verify against an uncached page.** After an update pass, a page cache can serve the old,
byte-identical page, so it reads as "nothing changed". Run `wpsite purge <site>`, then fetch
several pages (not just the home page) with a cache-busting query string and grep for
`fatal error|parse error`. How to prove a page is really fresh: `wp-studio:caching`.

**6. Never `wp config set … --raw` a string.** `wp config set WP_AUTO_UPDATE_CORE minor --raw`
writes an unquoted constant, a PHP fatal that takes down the site and WP-CLI with it (repair needs
a direct file edit). Use `--raw` only for `true`, `false` and numbers. The update policy needs no
`wp-config.php` constant at all.

**7. Leftover entries in `auto_update_plugins`.** Deleted plugins stay listed in the option. Harmless
once the policy forces updates, but they make the inventory lie; clean them as part of
`wp-studio:plugin-audit`.

## Hardening

`hardening.php` applies these, each switchable in its config block:

- XML-RPC off (and pingbacks, the `X-Pingback` header, the RSD link).
- Username enumeration blocked: `?author=N` redirects home; `/wp/v2/users` hidden from logged-out
  visitors.
- WordPress version removed from the page head and feeds.
- **Application Passwords off.** The studio reaches sites over SSH and WP-CLI only, so nothing needs
  them, and each one is a standing credential. If an outside service (a mobile app, an automation
  tool) needs the REST API with a password, set `WPSTUDIO_DISABLE_APP_PASSWORDS` to `false` in the
  deployed copy and redeploy.
- Security headers on front-end pages. First run `curl -sI https://<domain>/` and drop any header
  the host already sends. Strict-Transport-Security is deliberately not sent: it stays in browsers
  for its full lifetime and makes a later certificate problem an outage. That is the owner's call.
- Generic login error ("Invalid login."), so a failed login never confirms a username.
- `DISALLOW_FILE_EDIT` (dashboard code editors off; costs nothing, blocks no updates).
- Optional login throttle. Before turning it on, confirm `REMOTE_ADDR` is the visitor's address
  and not a proxy's; otherwise one attacker locks everyone out. Never key it on
  `X-Forwarded-For`, which any client can send.

**Do not:**
- **Set `DISALLOW_FILE_MODS`** on any site that is not patched by a person on a schedule. It makes
  `wp_is_file_mod_allowed( 'automatic_updater' )` false and the updater stops entirely (WordPress
  6.9.1 source). `hardening.php` fails its check if the constant is set.
- Run two login throttles (the plugin's and a security plugin's): it doubles the lockout.
- Count an `.htaccess` file as protection until you know the web server is Apache. **Nginx ignores
  `.htaccess` completely**, and most managed hosts run Nginx. Security and form plugins write
  `uploads/.htaccess` files that do nothing there.

### PHP must never run in uploads

This is the control that turns anything a scan misses into an inert file. It must be enforced by
the web server, and it must cover `.phtml`, `.phar` and `.pht`, not only `.php`. On one managed
host, `.php` under uploads returned 403 but `.phtml`, `.phar` and `.pht` were served (as text, not
run). Hosts that block `.php` often do not block the others.

Test it: deploy a harmless probe for each extension, fetch it, then remove it.
```
wpsite backup acme
printf '<?php echo "wpstudio-" . "probe-ran";' > projects/acme/work/probe.php     # also .phtml, .phar, .pht copies
wpsite deploy acme projects/acme/work/probe.php wp-content/uploads/wpstudio-probe.php
curl -s "https://<domain>/wp-content/uploads/wpstudio-probe.php"
wpsite sh acme 'rm -f wp-content/uploads/wpstudio-probe.*'
```
- Body `wpstudio-probe-ran`: **PHP executed. Fix it now.**
- Body showing the source (`"wpstudio-" . "probe-ran"`), a 403 or a 404: it did not execute.

To fix: on Apache 2.4, put this in `wp-content/uploads/.htaccess`:
```
<FilesMatch "\.(php[0-9]?|phtml|phar|pht|phps)$">
    Require all denied
</FilesMatch>
```
This works only where the server allows `.htaccess` overrides, so re-run the probe to confirm.
On Nginx you cannot fix it from WordPress. Ask the host to deny PHP execution under
`/wp-content/uploads/` for all of those extensions, then re-run the probe.

### Narrow every form upload field

A form plugin with a file-upload field is a top-tier entry point: these plugins get a critical
upload CVE every year or two, and their default allowlists are wide (one shipped a contact form
accepting 104 file types). Set each upload field to what the form needs, usually images and PDF.
Keep form plugins on automatic updates; that is the patch that matters when the next CVE lands.

### Patch the server's PHP too

A PHP-engine vulnerability (for example the October 2026 unauthenticated RCE fixed in PHP 8.5.12,
8.4.27, 8.3.36 and 8.2.35) cannot be fixed by any WordPress update. The host must update PHP and
restart PHP-FPM. On managed hosts, the CLI `php -v` and `wp cli info` are **not** the web PHP;
several FPM versions are installed and the site uses the one its hosting dashboard selects. On the
two managed hosts checked (2026-10), verify every installed FPM build, and that each FPM master
process started after that build (otherwise old workers still serve):
```
wpsite sh acme 'for f in /usr/sbin/php-fpm*; do "$f" -v | head -1; done; ps -eo lstart,args | grep "php-fpm: master" | grep -v grep'
```
If a build is old, or a master predates the patched build, ask the host to patch and restart. Also
flag a site whose PHP branch is near end of life (8.2 ends 2026-12-31) and plan the move to a
supported branch on staging.

## Related skills

- After a compromise: `wp-studio:malware-response` (harden only after cleanup).
- Removing plugins, and stale `auto_update_plugins` entries: `wp-studio:plugin-audit`.
