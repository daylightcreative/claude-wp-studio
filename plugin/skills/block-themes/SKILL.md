---
name: block-themes
description: Building and styling WordPress sites block-first — theme.json gotchas, content a non-technical client can edit without breaking, where custom CSS should live (mu-plugin, theme stylesheet, or Additional CSS), asset cache-busting, and small CSS fixes for phones. Use when building or editing a block theme or theme.json, adding custom CSS or a shortcode, when a client edit broke styling, when a button does nothing, or when text overflows or looks wrong on a phone.
---

# Block-first building

New work is block-first: a block theme, `theme.json` for design tokens, core blocks for content.
Moving an existing Divi site is the wp-studio:divi-to-blocks skill; images are wp-studio:images.

## theme.json and block theme gotchas

These were found on a custom block theme build (WordPress 6.x–7.x). Each one fails silently.

- **Use word slugs for presets, never slugs with digits.** WordPress builds CSS variable names
  with its kebab-case helper (`_wp_to_kebab_case`), which splits letters from digits: a font-size
  slug `h2` becomes `--wp--preset--font-size--h-2`. CSS that references `--…--h2` falls back
  silently. Name them `heading-large`, `body`, `small`. Check that every `var(--wp--preset--…)`
  your CSS uses exists in the rendered page.
- **`settings.spacing.blockGap: null` stops WordPress emitting block-gap margins.** Use it when
  your containers set their own flex or grid `gap`; otherwise flow-layout margins misalign flex
  children. (Observed behavior. The theme.json reference lists the type as boolean or null with
  default null but does not spell out null versus false; **UNVERIFIED** in the docs.)
- **Keep theme CSS unlayered.** WordPress's global styles are unlayered, and any rule inside
  `@layer` loses to unlayered CSS regardless of specificity.
- **Do not use core/cover's "content position" for layout.** It ships a high-specificity
  `width:auto` rule on the inner container; position the content with your own class.
- **New pattern files are invisible until the pattern cache is cleared.** WordPress caches a
  theme's pattern file list in a transient. Add this to every deploy that adds a pattern
  (`WP_Theme::delete_pattern_cache()`, since WordPress 6.4):

  ```bash
  wpsite wp acme eval 'wp_get_theme()->delete_pattern_cache();'
  ```

- **A fresh install has plain permalinks, so `/wp-json/` is not routed.** Use `?rest_route=/…`
  or set a structure: `wpsite wp acme rewrite structure '/%postname%/'`.
- **Version theme assets by file modification time.** A fixed `?ver=1.0.0` keeps the same URL,
  so browsers and CDNs keep serving the old file after a deploy:

  ```php
  $dir = get_stylesheet_directory();
  wp_enqueue_style( 'acme-theme', get_stylesheet_uri(), array(), filemtime( "$dir/style.css" ) );
  ```

## Content the client can edit without breaking

### Generate fragile markup with a shortcode

**Symptom:** the client changes only words in the block editor and a styled element falls apart
(a "label | value" panel collapses to one column, a copy button stops working).

**Cause:** the CSS depended on markup the editor cannot see — hidden `<span>` wrappers, or an
inline `<script>` that keys on the text. The editor does not preserve structure it cannot show.

**Fix:** register a shortcode in an mu-plugin that **regenerates** the markup from plain lines
the client edits (one `Label | Value` per line), and put any JavaScript in the plugin as one
delegated listener on `document`, enqueued only when the shortcode rendered. Convert existing
content with a backed-up WP-CLI rewrite.

**The wpautop trap:** the shortcode's `$content` arrives already wrapped in `<p>` and `<br>`.
In classic content `wpautop` runs on `the_content` at priority 10 and `do_shortcode` at 11; in
block content the Shortcode block's render callback runs `wpautop()` on its content itself. So
split on `/<br\s*\/?>|<\/p>\s*<p>|<\/?p>|\r\n|\n|\r/i` and `wp_strip_all_tags()` each line;
never assume raw newlines. Escape every value (`esc_html`, `esc_attr`) on output.

### The unlinked button

**Symptom:** a button looks perfect and does nothing. **Cause:** the client pasted the URL into
the block's **HTML anchor** field (Advanced, in the sidebar) instead of the link. The URL lands as
the wrapper's `id` and the `<a>` has no `href`; the editor gives no warning.

```bash
# site-wide, from stored content
wpsite wp acme db query "SELECT ID, post_title FROM wp_posts
  WHERE post_status='publish' AND post_content LIKE '%\"anchor\":\"http%'"
# one page, as rendered
curl -s "https://example.com/page/?cb=$RANDOM" | grep -o '<a class="wp-block-button__link[^>]*>' | grep -v 'href='
```

Fix: back up the post, remove the bogus `anchor`, put the URL on the `<a>` (and `linkTarget` /
`rel` in the block attributes if it opens a new tab). Tell the client the rule, not the incident:
"To link a button, select it and use the chain icon in the toolbar. After publishing, click the
button on the real page."

## Durable custom CSS: where it lives

**Rule: custom CSS that the site depends on lives in code the studio owns and deploys** — the
theme's stylesheet when the studio owns the theme, otherwise an mu-plugin. Additional CSS is
acceptable only where it demonstrably renders, edited by the procedure below.

| Situation | Put the CSS in |
|---|---|
| Studio-built or child theme | The theme's stylesheet, versioned with `filemtime` |
| Third-party or builder theme you do not own | An mu-plugin (`custom-styles.php`) |
| Divi 5 | An mu-plugin — Additional CSS was not output on a Divi 5 site (wp-studio:divi) |
| The client wants to tweak CSS themselves | Additional CSS, after confirming it renders |

Why an mu-plugin: files in `wp-content/mu-plugins/` load on every request, cannot be
deactivated from the dashboard, and no theme or plugin update touches them. Why not rely on
Additional CSS: it is stored as a `custom_css` post **per theme** (its title is the theme's
stylesheet slug), so switching or replacing the theme drops it; and some builders suppress it.

**The template:** `custom-styles.php` in this skill's folder. It enqueues on
`wp_enqueue_scripts` — either a sibling `.css` file versioned by `filemtime`, or inline CSS on a
handle registered with `src` false (the pattern core uses for its own global styles). Copy it to
`projects/<slug>/work/`, rename it with the project prefix, and deploy:

```bash
php -l projects/acme/work/acme-custom-styles.php
wpsite backup acme
wpsite deploy acme projects/acme/work/acme-custom-styles.php wp-content/mu-plugins/acme-custom-styles.php
wpsite deploy acme projects/acme/work/acme-custom-styles.css wp-content/mu-plugins/acme-custom-styles.css
wpsite purge acme
```

Only top-level PHP files in `mu-plugins/` load; a file inside a subfolder needs a loader.
Scope every rule to a page, template or component class. Load order only settles ties of equal
specificity; it never beats a more specific selector.

**Editing Additional CSS safely by WP-CLI** (works on classic themes; on block themes core merges
it into the `global-styles` inline stylesheet instead of a separate `wp-custom-css` tag):

1. Back up: `wpsite wp acme post list --post_type=custom_css --fields=ID,post_title`, then
   `wpsite backup acme --post <ID>`.
2. Change it server-side with an idempotent script — read with `wp_get_custom_css()`, append
   behind a marker comment only if the marker is absent, write with
   `wp_update_custom_css_post()`. Never paste the whole blob through the shell.
3. `wpsite purge acme` — the CSS is inlined in the page, so the page cache must clear.
4. Mirror the change into the project's stylesheet of record so the two do not drift.
5. Verify: `curl -s "https://example.com/?cb=$RANDOM" | grep -c 'your-marker'`.

## Small CSS lessons

**Mobile horizontal overflow — find the cause, do not mask it.** In the browser console at phone
width:

```js
[...document.querySelectorAll('*')]
  .filter(e => e.getBoundingClientRect().right > innerWidth + 1)
  .map(e => [e.tagName, e.className, Math.round(e.getBoundingClientRect().right)]);
```

Usual culprits: a desktop menu hidden with `visibility:hidden` but still laid out as a wide flex
row; a "full-bleed" image positioned with offsets and negative margins; and
`grid-template-columns: 1fr`, whose minimum is the item's min-content — use `minmax(0, 1fr)`,
`min-width:0` on grid items and `img { max-width:100% }`. `html { overflow-x: clip }` hides the
scrollbar but leaves the content cut off.

**iOS Safari enlarges text in narrow columns.** Some text (often accordion answers) renders
larger on an iPhone than in desktop or headless Chrome, at the same computed `font-size`. That is
Safari's text inflation, which runs when the page has not set `text-size-adjust`:

```css
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
```

It changes no authored sizes (MDN documents `none` as the opt-out; `100%` is what was used and
verified on a real device). Headless browsers do not reproduce the inflation, so check on an
iPhone. `custom-styles.php` ships this rule.

**Text vanishes on a colored section: color the innermost text node.** A rule like
`.section-dark p { color:#fff }` colors a white card's paragraph white. Setting a color on the
card wrapper does not help: an inherited value loses to any rule that targets the element
directly. Target the element that holds the text, at equal or higher specificity — for the
Post Excerpt block that is `.wp-block-post-excerpt__excerpt`, not `.wp-block-post-excerpt`.

**Measure, do not eyeball.** Confirm widths, alignment and overflow with
`getBoundingClientRect()` and `getComputedStyle()` on an uncached page (`?cb=<random>`), not a
downscaled screenshot.
