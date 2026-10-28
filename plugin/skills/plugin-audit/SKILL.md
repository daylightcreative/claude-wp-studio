---
name: plugin-audit
description: Audit a WordPress site's plugins and remove the dead weight completely — prove from the database whether an "active" plugin is actually used, find closed or abandoned plugins through the wordpress.org API, test removal on staging, check a plugin isn't the updater for others, take a security plugin's auto_prepend_file firewall out first, and clean leftover tables, options, auto-update entries and empty folders. Use when cleaning up a site, before removing or replacing a plugin, after a malware cleanup, when a plugin is flagged closed or vulnerable, or when the plugin list looks wrong.
---

# Plugin audit

**Rule: "active" is not "in use". Judge every plugin on evidence from the database and the
rendered pages, never on the plugin list, and prove a removal on staging before touching live.**
On one site every plugin was active and three were dead weight. Two others that intuition said
were removable were load-bearing: a form layout add-on owned a 17-row, 22-cell form layout
(removing it collapses the form to one column), and a conditional-logic add-on drove eleven real
conditions.

Every removal starts with `wpsite backup <site>` on the environment being changed.

## 1. Inventory

```
wpsite wp acme plugin list --fields=name,status,version,update_version,auto_update,wporg_status,wporg_last_updated
wpsite wp acme plugin list --status=must-use
wpsite wp acme plugin list --status=dropin
```
`wporg_status` (a documented `wp plugin list` field) is `active` for a live wordpress.org plugin,
`closed` for one wordpress.org has closed, and empty for one that was never there (premium or
custom), per the WP-CLI `extension-command` source (checked 2026-10-28).

**Check closed or abandoned plugins against wordpress.org directly** (run locally; it is a public
API, not a site call):
```
curl -s "https://api.wordpress.org/plugins/info/1.0/<slug>.json" | head -c 400
```
Responses, verified 2026-10-28:
- Live plugin: a JSON object with `version`, `last_updated`, `tested`, `requires_php` and more.
  A `last_updated` years old, or a `tested` several WordPress majors behind, means abandoned.
- Closed: `{"error":"closed", … "closed":true,"closed_date":"YYYY-MM-DD","reason":"…","reason_text":"…"}`.
- Never on wordpress.org: `{"error":"Plugin not found."}`. Check the vendor for those.

(The newer form `https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&request[slug]=<slug>`
returns the same data.)

A closed or abandoned plugin is a standing entry-point candidate. **Read its code**; a version
scanner will not tell you what it does. One closed add-on manager turned out to register an
unauthenticated webhook route on every request, and a filter that switched off TLS certificate
checks for all outbound WordPress HTTP requests whenever `WP_DEBUG` was on. Be precise with the
operator about severity: the TLS bypass was dormant (debug was off), but it would have fired the
moment someone turned debugging on to troubleshoot.

## 2. Prove whether it is used

Ask what the plugin produces, then look for that in the database. Read the plugin's own code to
learn its real storage keys; do not guess them (one form plugin keeps conditional logic under
the meta key `conditions`, and a `LIKE '%conditional%'` guess finds nothing).

| Plugin kind | Evidence to query |
|---|---|
| Page-builder module packs | Their shortcodes or blocks in content: `wpsite wp acme db query "SELECT COUNT(*) FROM wp_posts WHERE post_status NOT IN ('trash','auto-draft') AND post_content LIKE '%[prefix_%'"`, or `%<!-- wp:namespace/%` for blocks. Then list the distinct modules used |
| Form add-ons | The add-on's own keys in the form's stored settings (layout rows and cells, conditions, multi-part pages) for every form |
| Media types (SVG and similar) | Attachments of that MIME type, and whether content references them |
| Widgets | `wpsite wp acme option get sidebars_widgets` and the widget's own option |
| Anything with storage | Its tables (`SHOW TABLES LIKE 'wp_<prefix>%'`) and options holding real data |
| Front-end output | Fetch the pages it should affect and look for its markup or assets |

Use the site's real table prefix (`wpsite wp acme config get table_prefix`) in place of `wp_`.

## 3. Check it is not the updater for something else

Some plugins look like "the thing that keeps the premium add-ons current" and are not; others are.
Before deleting, find where the update code lives:
```
wpsite sh acme 'grep -rlE "Plugin_Updater|pre_set_site_transient_update_plugins" wp-content/plugins/<slug> wp-content/plugins/<parent-slug>'
```
On one site the add-on manager was not the updater: the Easy Digital Downloads-style updater lived
in the parent plugin and still loaded with the manager off. Confirm on staging by deactivating it
and firing the admin hooks as an administrator; expect no fatal error and no "requires …" notice:
```
wpsite wp acme:staging eval 'wp_set_current_user( <admin-id> ); do_action( "admin_menu" ); do_action( "admin_notices" );'
```
If it **is** the updater, keeping it is part of keeping the others patched
(`wp-studio:updates-and-hardening`, update trap 3).

## 4. Prove the removal on staging

Fingerprint what the plugin touches **structurally**, deactivate, fingerprint again, compare. Compare
structure (field counts, field types, layout rows and cells, condition counts, module lists), not
rendered bytes: asset changes alter the byte count harmlessly. For example, one line per form:
```
form#2  fields(24): …  layout: rows=17 cells=22  conditions: 11
```
Identical lines before and after mean it is safe. Then check the pages that use it, uncached
(`wpsite purge acme:staging`, then fetch with a cache-busting query string).

## 5. Remove it completely

`wp plugin delete` "deletes plugin files without deactivating or uninstalling" (WP-CLI docs), so
it leaves tables, options and firewall files behind. Order matters:

1. **Firewall first.** If a security plugin installed a WAF through `auto_prepend_file`, find the
   line (`.user.ini`, `php.ini` or `.htaccess` at the root) and revert it **before** removing the
   plugin, or every request fails with a fatal error once the prepended file is gone. PHP re-reads
   `.user.ini` every `user_ini.cache_ttl` seconds (default 300, per the PHP manual), so wait that
   long, confirm the site still loads, then delete the prepended file.
2. **Uninstall, don't just delete,** so the plugin's own cleanup runs:
   ```
   wpsite wp acme plugin uninstall <slug> --deactivate
   ```
3. **Clean what it left.** List first, confirm nothing else uses the prefix, save what you drop
   (the backup), then remove:
   ```
   wpsite wp acme db query "SHOW TABLES LIKE 'wp_<prefix>%'"
   wpsite wp acme db query "SELECT option_name FROM wp_options WHERE option_name LIKE '<prefix>%'"
   wpsite wp acme cron event list --fields=hook | grep -i <prefix>
   ```
   plus its folders outside `plugins/` (log folders under `wp-content`, firewall files at the
   root, folders under `uploads`). One security plugin left about 25 tables plus firewall files.
4. **Remove stale `auto_update_plugins` entries,** on every environment. Deleted plugins stay listed
   in that option, and a "ghost" entry for an uninstalled plugin makes the inventory lie:
   ```
   wpsite wp acme eval 'if ( ! function_exists( "get_plugins" ) ) { require_once ABSPATH . "wp-admin/includes/plugin.php"; } $keep = array_values( array_intersect( (array) get_site_option( "auto_update_plugins", array() ), array_keys( get_plugins() ) ) ); update_site_option( "auto_update_plugins", $keep ); print_r( $keep );'
   ```
5. **Find empty or unregistered plugin folders.** A cleanup that deletes files can leave a plugin's
   folder skeleton behind, which WordPress no longer sees as a plugin:
   ```
   wpsite wp acme eval 'if ( ! function_exists( "get_plugins" ) ) { require_once ABSPATH . "wp-admin/includes/plugin.php"; } $reg = array(); foreach ( array_keys( get_plugins() ) as $f ) { $reg[ strtok( $f, "/" ) ] = 1; } foreach ( scandir( WP_PLUGIN_DIR ) as $d ) { if ( "." === $d[0] || ! is_dir( WP_PLUGIN_DIR . "/$d" ) ) { continue; } if ( ! isset( $reg[ $d ] ) ) { echo "ORPHAN: $d\n"; } }'
   ```
   Look inside each before removing it: after an incident, an unregistered folder may be an implant
   (`wp-studio:malware-response`).
6. **Verify on the environment:** the pages from section 4 render the same, Site Health shows no new
   critical items, and `wpsite wp acme plugin list` matches what the operator expects.

Do it on staging, then live. Tell the operator in plain words what went and why: "Three plugins
were switched on but nothing on the site used them. Each one is extra code that can have security
holes, so I removed them after testing on the staging copy."

## Notes

- A "closed" or "not found" answer for a premium plugin is not alarming by itself; check the
  vendor's changelog and that the licence still delivers updates.
- Record what was removed, the evidence, and the date in the project's `CLAUDE.md`.
