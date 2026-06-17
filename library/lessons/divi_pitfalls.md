# Divi Pitfalls (Why We Lean Away From It)

**Date**: 2026-06-15
**Status**: Active
**Scope**: The recurring Divi problems that make it more trouble than it's worth, plus the facts you need to work on an existing Divi site safely. Background for the Divi→Gutenberg migration.

Divi is a powerful page builder and plenty of beautiful sites are built with it. But across
many client sites it has produced a recurring family of fragile, time-eating problems.
Now that the design can be built directly in native WordPress blocks, **new work is
Gutenberg-first** and we migrate existing sites off Divi when it makes sense. See
[Divi → Gutenberg](../playbooks/divi_to_gutenberg.md).

## The recurring problems

### Front-end runtime is fragile (Divi 5)

Divi 5's front-end JavaScript for **entrance animations** (`.et_animated`) and
**"interactions"** (click-to-toggle popups, `data-interaction-trigger`) has failed to
initialize on real sites — with **no JS errors and all assets returning 200**. Symptoms:
animated elements stay stuck invisible (`opacity:0`), and click popups never open (and,
worse, their hidden state never applies, so they leak into the page).

**Workaround when you must keep the Divi site:** fix it yourself in an mu-plugin — force
`.et_animated{opacity:1}`, hide the popups by default, and reimplement the behavior with
your own JS (a `window` capture-phase click listener that calls
`stopImmediatePropagation()` to preempt Divi's broken handler). See
[custom CSS in an mu-plugin](custom_css_belongs_in_mu_plugin.md).

### Version updates break things

Updating Divi has broken production. A **5.6.2 → 5.7.0** update broke the global Theme
Builder header (SVG logo collapsed to 0 height; responsive show/hide stopped, so desktop
and mobile nav both rendered). The fix was to **roll back and pin**:

- **Pin the Divi version and turn WP auto-update OFF** on production.
- Test any Divi update on a **staging copy** first; verify the header/nav/logo before
  promoting.

### Custom CSS is suppressed

Divi 5 does not output `et_divi[custom_css]` on the front end (and core "Additional CSS" was
suppressed too). Put custom CSS in an mu-plugin instead —
[here's why and how](custom_css_belongs_in_mu_plugin.md).

### Old plugins call dead Divi 4 classes

Divi-ecosystem plugins (e.g. Divi Overlays) sometimes call Divi 4 classes
(`ET_Builder_Element`) that Divi 5 only loads conditionally → intermittent 500 fatals on
uncached requests. Patchable by adding a `class_exists()` guard, **but a plugin update wipes
the patch** — re-test after updates. Another reason to reduce Divi-ecosystem surface area.

## Facts you need to work on an existing Divi site

### Divi 4 vs Divi 5 store content completely differently

- **Divi 4:** pages are **shortcodes** — `[et_pb_section][et_pb_row][et_pb_text]…`. You
  extract content by parsing shortcodes.
- **Divi 5:** pages are **Gutenberg-style block comments** — `<!-- wp:divi/* -->` whose
  attributes are deeply nested JSON, including `$variable(...)$` design-token references.
  This is **not** the shortcode format — old `et_pb_*` string searches find nothing.

Check which you're dealing with first: `./wp.sh post get <ID> --field=content` and look at
the markup. This determines the whole extraction approach in a migration.

### Divi is premium — installing a specific version

Divi isn't on wp.org. To get an exact version (e.g. to roll back), download from the Elegant
Themes API using the license stored in the site's `et_automatic_updates_options` DB option
(a username + 40-char api_key):

```
curl -sSL "https://www.elegantthemes.com/api/api_downloads.php?api_update=1&theme=Divi&api_key=KEY&username=USER&version=X.Y.Z"
```

The **`&version=` parameter is essential** — omit it and you get the account's channel
default (which may be an old Divi 4 build). Verify the zip's `Divi/style.css` version, then
`wp theme install <zip> --force`, clear `et-cache`, purge the host cache. Not every version
is served on every channel.

### Theme Builder = global header/footer/templates

Divi's global header, footer, and templated areas live in the **Theme Builder** (`tb-*`
templates), separate from page content. A migration has to recreate these as block template
parts, not just convert page bodies. Don't forget them.
