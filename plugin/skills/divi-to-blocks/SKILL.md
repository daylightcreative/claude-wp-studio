---
name: divi-to-blocks
description: The playbook for moving a site off Divi onto a block theme and core blocks, from a scoping estimate through page conversion, migration QA (text diff, URL parity, redirects, 404 buckets) and removing Divi. Use when the operator asks how much work a Divi-to-Gutenberg move is, to plan or run the migration, or to check a finished migration for lost content or broken URLs.
---

# Divi → blocks migration

Goal: the same design and content on a block theme with core blocks, so the site is faster and
the client can edit it without breaking it. Divi facts this playbook relies on (Divi 4 vs 5
formats, Theme Builder, `et-cache`) are in the wp-studio:divi skill; building on blocks is the
wp-studio:block-themes skill; images are the wp-studio:images skill.

**Order is fixed:** Phase 0 estimate → operator go/no-go → build on **staging** → QA → cut over →
remove Divi last. Never convert on the live site.

## Phase 0 — Estimate (no changes)

Answer "how much work is this?" with a page-by-page estimate before touching anything. Dispatch the
`site-scout` agent for the inventory, or run it yourself:

```bash
wpsite check acme
wpsite wp acme post list --post_type=page --fields=ID,post_name,post_title,post_status --format=csv
wpsite wp acme post list --post_type=post --post_status=publish --format=count
wpsite wp acme post-type list --fields=name,hierarchical,public
wpsite wp acme post get 123 --field=content | head -c 400      # Divi 4 shortcodes or Divi 5 blocks?
```

1. **Content inventory:** pages, posts, custom post types, and whether each type is hierarchical
   (this matters for redirects, Phase 4).
2. **Divi era** — decides how content is extracted (see wp-studio:divi).
3. **Global pieces:** Theme Builder header, footer and post templates; Divi Library global
   modules. These become template parts and synced patterns, not page bodies.
4. **Module catalog per page.** Easy: text, headings, images, buttons, columns, galleries. Hard
   (each turns an hour into a day): sliders, animations/parallax, tabs, forms, dynamic loops,
   pricing tables, maps, lightboxes.
5. **Visual baseline:** screenshot every page at desktop and phone width.
6. **The URL set** (Phase 4 needs it, and the old site may not survive the move): save the old
   `sitemap.xml`, ask the operator for a Search Console page export, and pull the Wayback list.
7. **Report:** a table of every page with Easy / Medium / Hard and why, the global pieces, the
   decisions the operator must make (slider, tabs, forms), and an effort estimate. Get go/no-go.

Plain words for the operator: "Text, pictures, buttons and columns move quickly. The hours go
into the header and footer, any sliders, tabs or forms, and matching the look closely."

## Phase 1 — Design tokens, once, serially

Write the block theme's `theme.json` (palette, font families, type scale, spacing scale, content
widths) **before any page is converted, by one author.** Pull the values from the Divi design
(Divi 5 `$variable()$` tokens map to global colors and fonts; Divi 4 keeps them in Theme Options
and module settings). Every converted page references these presets, so changing them later
means re-touching every page. Follow the theme.json rules in wp-studio:block-themes (word slugs,
not digit slugs).

## Phase 2 — Convert pages (fan out)

Once `theme.json` and the template parts exist on staging, convert pages in parallel: dispatch one
`page-converter` agent per page (or small batch), lowest-risk pages first. Each converter:

1. Backs up the page: `wpsite backup acme:staging --post 123`.
2. Extracts the real content (Divi 4: parse shortcodes; Divi 5: parse the block JSON).
3. Rebuilds it as core blocks using the mapping below and the shared presets only — no new
   colors or sizes invented per page.
4. Fixes empty `alt` text, rewrites internal links, and wires every image to its Media Library
   attachment (wp-studio:images, "Hand-written `<img>`").
5. Writes the content and reports the page ID, what was not mapped, and any decision needed.

```bash
wpsite backup acme:staging --post 123
wpsite wp acme:staging --input projects/acme/work/pages/123.html post update 123 - --user=<admin_login>
```

`-` makes `wp post update` read the new `post_content` from the file sent with `--input`.

| Divi module | Core block |
|---|---|
| Section / Row / Column | Group / Columns |
| Text | Paragraph and Heading (split run-together text into separate blocks) |
| Image | Image, tied to its attachment |
| Button | Buttons (the link goes on the button, not the HTML anchor field) |
| Blurb | Group with Image + Heading + Paragraph |
| Gallery | Gallery |
| Video | Video or Embed |
| Toggle / Accordion | Details |
| Tabs | No core block: a focused block plugin, or redesign |
| Slider / Carousel | No core block: static stack, a slider block plugin, or redesign |
| Call To Action | Group or Cover + Heading + Paragraph + Buttons |
| Pricing table | Columns of Groups |
| Contact form | A forms plugin, rebuilt field for field |
| Blog / post loops | Query Loop |
| Code | Custom HTML |
| Global module | Synced pattern |

## Phase 3 — Global templates and forms

- Rebuild the Theme Builder header, footer and templates as block template parts. Usually the
  largest single piece of work; match nav, logo and phone behavior to the baseline.
- Rebuild each Divi form in a forms plugin. Read the live form first and match fields, labels,
  required flags and notifications exactly. Test on staging with outgoing mail intercepted.
- List every Divi-ecosystem plugin and decide replace or remove.

## Phase 4 — Migration QA (before sign-off)

Run the `qa-checker` agent against staging, or do these yourself. Read every check against an
uncached page (`?cb=<random>` after `wpsite purge`).

### Content completeness: text diff, old vs new, every URL

A rebuild can silently drop content (one page lost 2 of 5 items unnoticed until the client saw
it). For every page and post, fetch the old URL and the new URL, strip `script`, `style`, `svg`,
`header`, `footer` and `nav`, split the text into sentence chunks of 7+ words, normalize
(lowercase, letters and digits only), and list old chunks whose first ~55 normalized characters
are not in the new page. Triage before calling anything a loss:

- **Category → detail restructure:** the copy moved to sub-pages that audit clean.
- **Intentional rewrite:** confirm the idea is present.
- **Chunk boundary:** the old site ran heading + first sentence together; check a distinctive
  tail phrase instead.

A real drop is a substantial chunk with no match anywhere on the page. Restore it from the old
site and re-run the diff.

### URL parity: build the expected set from more than the database

Combine: the old `sitemap.xml`, the Search Console page export, the Wayback CDX list, and access
logs if the host keeps them (those show what got traffic).

```bash
curl -s 'http://web.archive.org/cdx/search/cdx?url=example.com/*&fl=original&collapse=urlkey&filter=statuscode:200&output=json' > work/wayback-urls.json
```

Crawl staging, request every expected path, and deliver a **URL parity report** (path, old
status, new status, redirect target) rather than an assurance.

### Redirects WordPress will not make for you

WordPress records an old slug and redirects it (`_wp_old_slug`) only for **published,
non-hierarchical** post types. Core's `wp_check_for_changed_slugs()` returns early for any
hierarchical type, so:

- **Pages** and **hierarchical custom post types**: a changed slug or parent just 404s.
- **Category, tag and other term slugs**: no automatic redirect either.
- Posts and non-hierarchical post types: redirected automatically.

Add an explicit 301 (in the site's redirect plugin or SEO plugin) for every changed URL in the
parity report.

### Bucket the 404s after launch

Watch 404s for a few weeks (an SEO plugin's 404 monitor, or the host's access logs) and sort them
into buckets, not one-by-one fixes:

| Bucket | Typical action |
|---|---|
| Expired items under one path (old events) | One wildcard redirect to the listing page |
| Old CMS structure (`/articles/…`) | Wildcard redirect to the new section |
| Old structure, specific pages | Individual 301s |
| Removed pages, low traffic | Leave, or redirect individually |
| Items whose target needs a business answer | Ask the operator; park until answered |
| Bot noise (`about:blank`, probe paths) | Exclude from the monitor; no action |

On one site "page not found" was the 4th most-visited page before this cleanup.

### Visual and functional

Every page at desktop and phone width against the Phase 0 baseline; every form submitted; every
button clicked on the rendered page. Then operator sign-off.

## Phase 5 — Cut over and remove Divi

1. Fresh database backup of production (`wpsite backup acme`).
2. Promote staging, switch the active theme to the block theme.
3. Only now deactivate and delete Divi and its add-ons.
4. **Scrub remnants:** with Divi gone, any `[et_pb_*]` shortcode left in content prints as raw
   text, and an empty excerpt builds its summary from it.

   ```bash
   wpsite wp acme db query "SELECT ID, post_type, post_title FROM wp_posts
     WHERE post_status='publish' AND post_content LIKE '%[et_pb_%'"
   ```

5. Delete `wp-content/et-cache/`, `wpsite purge acme`, re-run the URL parity check on production.
6. Record in the project's `CLAUDE.md` that the site is now a block theme without Divi.

## Tell the operator up front

- Close visual match is the slow part; pixel-perfect is not the goal, the agreed look is.
- Sliders, tabs and fancy animations have no core equivalent; each is a small design decision.
- Forms are rebuilt and re-tested, not copied.
