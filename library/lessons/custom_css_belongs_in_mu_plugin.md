# Custom CSS Belongs in an mu-plugin (Not the Customizer)

**Date**: 2026-06-15
**Status**: Active
**Scope**: Where to put custom CSS on a client WordPress site so it's reliable and survives updates — and why the obvious places fail.

The reliable, update-proof home for custom CSS is a **must-use plugin (mu-plugin)** that
prints a `<style>` block on `wp_head`. The "obvious" places — the Customizer's *Additional
CSS* box and a page builder's own custom-CSS field — are **not reliable**, especially on
Divi sites.

## Why not the Customizer / builder box

- On Divi 5 sites, the theme's `et_divi[custom_css]` is **not output on the front end**, and
  WordPress core's "Additional CSS" (`wp_update_custom_css_post`) has been seen **suppressed**
  too — both verified missing from the served HTML on a real site. CSS pasted there silently
  does nothing.
- Even when it works, builder/Customizer CSS can be overwritten by theme updates, child-theme
  changes, or a builder migration.

## Why an mu-plugin wins

- `wp-content/mu-plugins/` files load automatically on every request and are **never touched
  by theme or plugin updates**. They can't be deactivated from the dashboard.
- Hooked late on `wp_head` (e.g. priority 99), the `<style>` block wins specificity battles
  against theme CSS that loaded earlier.
- No build step, no activation. Edit locally, upload, done.

A ready template is in `tooling/templates/mu-plugin-css.php`.

## The deploy ritual (do not skip the lint)

1. Edit the mu-plugin locally.
2. **`php -l <file>.php`** — lint it. ⚠️ **A PHP syntax error in any mu-plugin fatals the
   ENTIRE site** (white screen for every visitor). Never upload unlinted PHP.
3. Upload to the server's `wp-content/mu-plugins/` via scp/SFTP. Live immediately.
4. Purge the cache (see [caching by host](caching_by_host.md)).

## Same pattern for behavior, not just CSS

When a theme/builder's front-end JS is broken or unreliable, the same mu-plugin pattern fixes
it: reimplement the behavior in your own small script printed from the mu-plugin. (On Lindale,
Divi 5's animation + "interactions" runtime didn't initialize, so an mu-plugin forced the
hidden elements visible and reimplemented the popups with plain JS.) See
[Divi pitfalls](divi_pitfalls.md).

## Keep it scoped

Scope every rule to specific selectors / page classes so styles don't leak site-wide. Keep
one mu-plugin per concern with a clear `Plugin Name` header so it's easy to find later.
